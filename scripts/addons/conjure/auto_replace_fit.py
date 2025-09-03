# auto_replace_fit.py
# CONJURE integration: convex-hull alignment + rigid ICP refinement for mesh replacement
# Integrated from standalone auto_replace_fit.py for better mesh fitting in CONJURE

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

# ---------------------------
# Internal utilities
# ---------------------------

def _depsgraph(ctx=None):
    return (ctx or bpy.context).evaluated_depsgraph_get()

def _to_evaluated_mesh(obj, ctx=None):
    """
    Returns (obj_eval, mesh_eval). Caller MUST clear with obj_eval.to_mesh_clear().
    Respects modifiers (evaluated depsgraph).
    """
    dg = _depsgraph(ctx)
    obj_eval = obj.evaluated_get(dg)
    try:
        me = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
    except TypeError:
        me = obj_eval.to_mesh()
    return obj_eval, me

def _convex_hull_world_stats(obj, ctx=None):
    """
    Build convex hull (in object local), then return world-space stats:
      pts_world : (N,3) numpy float64
      centroid  : (3,)
      A         : (3,3) PCA basis (columns), right-handed
      extents   : (3,) min->max size along PCA axes (in world units)
    """
    if obj.type != 'MESH':
        raise TypeError(f"{obj.name} is not a mesh")

    obj_eval, me = _to_evaluated_mesh(obj, ctx)
    bm = bmesh.new()
    bm.from_mesh(me)

    # Robust across Blender versions (some don't accept delete_unused)
    try:
        bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False, delete_unused=True)
    except TypeError:
        bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)

    mw = obj_eval.matrix_world
    pts = np.array([(mw @ v.co).to_tuple() for v in bm.verts], dtype=np.float64)

    bm.free()
    obj_eval.to_mesh_clear()

    if pts.shape[0] < 3:
        # Degenerate: return safe defaults around object origin
        centroid = pts.mean(axis=0) if pts.size else np.array((mw.translation.x, mw.translation.y, mw.translation.z))
        A = np.eye(3, dtype=np.float64)
        extents = np.array([1e-6, 1e-6, 1e-6], dtype=np.float64)
        return pts, centroid, A, extents

    centroid = pts.mean(axis=0)
    centered = pts - centroid
    cov = np.cov(centered.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    A = evecs[:, order]  # columns are principal directions (world)
    # ensure right-handed basis (avoid reflections)
    if np.linalg.det(A) < 0:
        A[:, 2] *= -1.0

    # extents along PCA axes
    proj = centered @ A  # N x 3 in PCA space
    mins = proj.min(axis=0)
    maxs = proj.max(axis=0)
    extents = (maxs - mins) + 1e-12  # avoid zeros
    return pts, centroid, A, extents

def _uniform_scale_from_extents(ext_target, ext_source):
    """
    Compute a robust uniform scale from per-axis size ratios.
    We use the geometric mean (balanced, less sensitive to outliers).
    """
    ratios = np.array(ext_target, dtype=np.float64) / np.array(ext_source, dtype=np.float64)
    ratios = np.clip(ratios, 1e-9, 1e12)
    return float(np.prod(ratios) ** (1.0 / 3.0))

def _compose_similarity(src_centroid, tgt_centroid, R, s):
    """Return 4x4 Matrix M = T(tgt) * R * S(s) * T(-src)."""
    T_to_origin = Matrix.Translation(Vector(-src_centroid))
    T_to_target = Matrix.Translation(Vector(tgt_centroid))
    R4 = Matrix(((R[0,0], R[0,1], R[0,2], 0.0),
                 (R[1,0], R[1,1], R[1,2], 0.0),
                 (R[2,0], R[2,1], R[2,2], 0.0),
                 (0.0, 0.0, 0.0, 1.0)))
    S4 = Matrix.Scale(float(s), 4)
    return T_to_target @ R4 @ S4 @ T_to_origin

def _apply_delta_matrix(obj, M_delta, *, apply_to_object_matrix=True):
    """
    If apply_to_object_matrix: multiply obj.matrix_world by M_delta (preferred).
    Otherwise, bake into mesh data (keeps world matrix).
    """
    if apply_to_object_matrix:
        obj.matrix_world = M_delta @ obj.matrix_world
    else:
        mw = obj.matrix_world.copy()
        obj.data.transform(M_delta)
        obj.matrix_world = mw

def _transform_points(M4, P):
    """
    Robustly apply a Blender 4x4 Matrix (column-vector convention) to an Nx3 NumPy array.
    Returns an Nx3 NumPy array.
    """
    out = np.empty_like(P, dtype=np.float64)
    for i in range(P.shape[0]):
        v4 = M4 @ Vector((P[i,0], P[i,1], P[i,2], 1.0))
        out[i, 0] = v4[0]
        out[i, 1] = v4[1]
        out[i, 2] = v4[2]
    return out

def _sample_surface_points_world(obj, count=3000, seed=0, ctx=None):
    """
    Uniform surface sampling (triangle-area weighted), returns (N,3) world-space points.
    Respects modifiers (evaluated mesh).
    """
    rng = np.random.default_rng(int(seed))
    obj_eval, me = _to_evaluated_mesh(obj, ctx)
    me.calc_loop_triangles()

    mw = obj_eval.matrix_world
    verts_world = np.array([ (mw @ v.co).to_tuple() for v in me.vertices ], dtype=np.float64)
    tris = [lt.vertices for lt in me.loop_triangles]
    if not tris:
        obj_eval.to_mesh_clear()
        return verts_world.copy()

    idx = np.array(tris, dtype=np.int32)
    v0 = verts_world[idx[:,0]]
    v1 = verts_world[idx[:,1]]
    v2 = verts_world[idx[:,2]]
    areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    total_area = float(areas.sum())
    if total_area <= 0:
        obj_eval.to_mesh_clear()
        return verts_world.copy()

    probs = areas / total_area
    tri_ids = rng.choice(len(tris), size=count, p=probs, replace=True)

    r1 = rng.random(count)
    r2 = rng.random(count)
    sqrt_r1 = np.sqrt(r1)
    u = 1.0 - sqrt_r1
    v = r2 * sqrt_r1
    w = 1.0 - u - v

    P = u[:,None] * v0[tri_ids] + v[:,None] * v1[tri_ids] + w[:,None] * v2[tri_ids]

    obj_eval.to_mesh_clear()
    return P

def _kabsch_umeyama(X, Y, with_scale=False):
    """
    Solve for Y ≈ (s) R X + t.
    Returns (s, R, t). If with_scale=False, s=1.0 (rigid).
    """
    X = np.asarray(X, dtype=np.float64)
    Y = np.asarray(Y, dtype=np.float64)
    n = X.shape[0]

    muX = X.mean(axis=0)
    muY = Y.mean(axis=0)
    Xc = X - muX
    Yc = Y - muY

    cov = (Xc.T @ Yc) / max(n, 1)
    U, S, Vt = np.linalg.svd(cov)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T

    if with_scale:
        varX = (Xc**2).sum() / max(n, 1)
        s = float(S.sum() / max(varX, 1e-12))
    else:
        s = 1.0

    t = muY - s * (R @ muX)
    return s, R, t

def _icp_rigid(source_pts, target_pts, iters=15, trim_ratio=0.15):
    """
    Classic ICP with nearest neighbors and robust trimming, **rigid only** (no scale).
    Returns a Blender 4x4 Matrix mapping source -> target.
    """
    kd = KDTree(len(target_pts))
    for i, p in enumerate(target_pts):
        kd.insert(Vector(p), i)
    kd.balance()

    M = Matrix.Identity(4)

    for _ in range(max(1, iters)):
        X = _transform_points(M, source_pts)

        Y = np.empty_like(X)
        d = np.empty((X.shape[0],), dtype=np.float64)
        for i, p in enumerate(X):
            _, idx, dist = kd.find(Vector(p))
            Y[i] = target_pts[idx]
            d[i] = dist

        if 0.0 < trim_ratio < 0.49:
            thr = float(np.quantile(d, 1.0 - trim_ratio))
            mask = d <= thr
            X_used = X[mask]
            Y_used = Y[mask]
        else:
            X_used, Y_used = X, Y

        _, R, t = _kabsch_umeyama(X_used, Y_used, with_scale=False)  # rigid
        R4 = Matrix(((R[0,0], R[0,1], R[0,2], 0.0),
                     (R[1,0], R[1,1], R[1,2], 0.0),
                     (R[2,0], R[2,1], R[2,2], 0.0),
                     (0.0,    0.0,    0.0,    1.0)))
        T4 = Matrix.Translation(Vector(t))

        M = (T4 @ R4) @ M

    return M

# ---------------------------
# CONJURE-specific functions
# ---------------------------

def create_combined_mesh_from_objects(mesh_objects, name="CombinedMesh"):
    """
    Create a single temporary mesh object from multiple mesh objects.
    This treats all imported meshes as a single unit for alignment purposes.
    """
    print(f"🔗 Combining {len(mesh_objects)} meshes into single object for alignment...")
    
    # Create a new mesh
    combined_mesh = bpy.data.meshes.new(name)
    combined_obj = bpy.data.objects.new(name, combined_mesh)
    
    # Combine all mesh data
    bm = bmesh.new()
    
    for obj in mesh_objects:
        if obj.type != 'MESH':
            continue
            
        # Get object's world matrix
        obj_matrix = obj.matrix_world
        
        # Create temporary bmesh from object
        temp_bm = bmesh.new()
        temp_bm.from_mesh(obj.data)
        
        # Transform vertices to world space, then to combined object's local space
        for vert in temp_bm.verts:
            vert.co = obj_matrix @ vert.co
        
        # Merge into combined bmesh
        bm.from_mesh(temp_bm.to_mesh())
        temp_bm.free()
    
    # Apply to combined mesh
    bm.to_mesh(combined_mesh)
    bm.free()
    
    # Add to scene temporarily
    bpy.context.collection.objects.link(combined_obj)
    
    print(f"✅ Created combined mesh with {len(combined_mesh.vertices)} vertices")
    return combined_obj

def apply_transform_to_mesh_group(mesh_objects, transform_matrix):
    """
    Apply the same transformation matrix to all objects in a group.
    This ensures all imported meshes move together as a unit.
    """
    print(f"🔄 Applying transformation to {len(mesh_objects)} mesh objects...")
    
    for obj in mesh_objects:
        if obj.type != 'MESH':
            continue
        
        # Apply the transformation
        _apply_delta_matrix(obj, transform_matrix, apply_to_object_matrix=True)
        print(f"   ✅ Transformed {obj.name}")
    
    print("✅ All meshes transformed successfully")

def auto_replace_fit_conjure(old_mesh_obj, new_mesh_objects, **kwargs):
    """
    CONJURE-specific version of auto_replace_fit that handles multiple new meshes.
    
    Args:
        old_mesh_obj: The existing "Mesh" object (target)
        new_mesh_objects: List of newly imported mesh objects (sources)
        **kwargs: Additional parameters for auto_replace_fit
    
    Returns:
        Matrix: The transformation matrix applied to align new meshes to old mesh
    """
    if not old_mesh_obj or not new_mesh_objects:
        raise ValueError("Both old_mesh_obj and new_mesh_objects must be provided")
    
    if old_mesh_obj.type != 'MESH':
        raise TypeError("old_mesh_obj must be a MESH object")
    
    print(f"🎯 CONJURE Auto Replace Fit:")
    print(f"   📍 Target (old): {old_mesh_obj.name}")
    print(f"   📦 Sources (new): {[obj.name for obj in new_mesh_objects if obj.type == 'MESH']}")
    
    # Filter to only mesh objects
    mesh_objects = [obj for obj in new_mesh_objects if obj.type == 'MESH']
    if not mesh_objects:
        raise ValueError("No valid mesh objects found in new_mesh_objects")
    
    try:
        # Create a temporary combined mesh from all new objects
        combined_obj = create_combined_mesh_from_objects(mesh_objects, "TempCombinedForAlignment")
        
        # Use the standard auto_replace_fit on the combined mesh
        print("🔧 Running auto_replace_fit alignment...")
        transform_matrix = auto_replace_fit(
            old_obj=old_mesh_obj,
            new_obj=combined_obj,
            apply=False,  # Don't apply to combined object
            **kwargs
        )
        
        # Apply the transformation to all individual mesh objects
        apply_transform_to_mesh_group(mesh_objects, transform_matrix)
        
        # Clean up the temporary combined object
        bpy.data.objects.remove(combined_obj, do_unlink=True)
        bpy.data.meshes.remove(combined_obj.data, do_unlink=True)
        print("🧹 Cleaned up temporary combined mesh")
        
        print("🎉 CONJURE Auto Replace Fit completed successfully!")
        return transform_matrix
        
    except Exception as e:
        # Clean up on error
        try:
            if 'combined_obj' in locals():
                bpy.data.objects.remove(combined_obj, do_unlink=True)
                bpy.data.meshes.remove(combined_obj.data, do_unlink=True)
        except:
            pass
        raise e

# ---------------------------
# Public API (from original auto_replace_fit.py)
# ---------------------------

def auto_replace_fit(old_obj,
                     new_obj,
                     *,
                     icp_points=3000,
                     icp_iters=15,
                     icp_trim=0.15,
                     seed=0,
                     apply=True):
    """
    Align `new_obj` to `old_obj` in world space:
      1) Convex-hull fit (centroid + PCA axes + **uniform scale** via geometric mean)
      2) Rigid ICP refinement (R + t only; **no scale**)

    Args:
        old_obj (Object): reference mesh (target)
        new_obj (Object): mesh to be aligned (source)
        icp_points (int): number of sampled surface points per mesh (WORLD)
        icp_iters (int): ICP iterations
        icp_trim (float): fraction [0..0.49] to trim worst residuals each iteration
        seed (int): RNG seed for surface sampling
        apply (bool): if True, writes the transform into new_obj.matrix_world

    Returns:
        Matrix: total 4x4 transform M_total mapping NEW → OLD in world space.

    Raises:
        TypeError / ValueError on invalid inputs.
    """
    if old_obj is None or new_obj is None:
        raise ValueError("old_obj and new_obj must be valid Blender mesh objects.")
    if old_obj.type != 'MESH' or new_obj.type != 'MESH':
        raise TypeError("Both old_obj and new_obj must be MESH objects.")

    # ---- 1) Convex-hull fit ----
    _, c_old, A_old, e_old = _convex_hull_world_stats(old_obj)
    _, c_new, A_new, e_new = _convex_hull_world_stats(new_obj)

    # rotation from NEW -> OLD PCA bases; avoid reflection
    R0 = A_old @ A_new.T
    if np.linalg.det(R0) < 0:
        A_new_fix = A_new.copy()
        A_new_fix[:, 2] *= -1.0
        R0 = A_old @ A_new_fix.T

    s0 = _uniform_scale_from_extents(e_old, e_new)
    M0 = _compose_similarity(c_new, c_old, R0, s0)

    # ---- 2) Rigid ICP refinement (no scale) ----
    P_src = _sample_surface_points_world(new_obj, count=icp_points, seed=seed)
    P_tgt = _sample_surface_points_world(old_obj, count=icp_points, seed=seed + 1)

    if P_src.shape[0] < 3 or P_tgt.shape[0] < 3:
        # Not enough points to run ICP; fall back to hull-only
        M_total = M0
    else:
        # Start ICP from the hull-aligned source
        M_icp = _icp_rigid(
            source_pts=_transform_points(M0, P_src),
            target_pts=P_tgt,
            iters=icp_iters,
            trim_ratio=icp_trim
        )
        M_total = M_icp @ M0

    if apply:
        _apply_delta_matrix(new_obj, M_total, apply_to_object_matrix=True)

    return M_total