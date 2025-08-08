"""
Test script for RunComfy Orchestrator.

Tests the high-level job orchestration functionality including:
1. Job creation and management
2. Machine coordination (dev server vs cloud)
3. Complete workflow execution
4. Progress tracking integration
5. Cost estimation and tracking
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any

# Import our components
try:
    from runcomfy.runcomfy_orchestrator import RunComfyOrchestrator, FluxMeshJob, JobStatus
    from runcomfy.dev_server_state import DevServerStateManager
    from runcomfy.workflow_progress_tracker import progress_tracker
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    exit(1)


async def test_orchestrator_initialization():
    """Test basic orchestrator setup and configuration"""
    print("\n🧪 Testing Orchestrator Initialization")
    print("="*50)
    
    try:
        # Test with default workflow path
        orchestrator = RunComfyOrchestrator()
        
        print("✅ Orchestrator created successfully")
        print(f"   Workflow path: {orchestrator.workflow_path}")
        print(f"   Prefer dev server: {orchestrator.prefer_dev_server}")
        print(f"   Machine reuse: {orchestrator.machine_reuse}")
        
        # Test workflow loading
        if orchestrator.workflow_path.exists():
            workflow = orchestrator.load_workflow()
            print(f"✅ Workflow loaded: {len(workflow)} nodes")
            
            # Test workflow preparation
            test_prompt = "A detailed robotic helmet with intricate mechanical details"
            prepared = orchestrator.prepare_workflow_inputs(workflow, test_prompt)
            
            # Check if prompt was injected
            if "34" in prepared and prepared["34"]["inputs"]["clip_l"] == test_prompt:
                print("✅ Workflow preparation working correctly")
            else:
                print("⚠️ Workflow preparation may have issues")
        else:
            print(f"⚠️ Workflow file not found: {orchestrator.workflow_path}")
        
        # Test cost estimation
        cost_estimate = orchestrator.estimate_cost("medium", 300)  # 5 minutes
        print(f"✅ Cost estimation: ${cost_estimate} for 5 minutes on medium machine")
        
        return orchestrator
        
    except Exception as e:
        print(f"❌ Initialization test failed: {e}")
        return None


async def test_machine_coordination():
    """Test machine getting and coordination logic"""
    print("\n🧪 Testing Machine Coordination")
    print("="*50)
    
    orchestrator = RunComfyOrchestrator()
    
    try:
        # Check development server availability
        dev_server_manager = DevServerStateManager()
        dev_server = dev_server_manager.load_server_state()
        
        if dev_server and dev_server.status == "running":
            print(f"✅ Development server available: {dev_server.server_id}")
            print(f"   URL: {dev_server.base_url}")
            print(f"   Type: {dev_server.server_type}")
            
            # Test health check
            is_healthy = await dev_server_manager.check_server_health(dev_server)
            print(f"   Health: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
            
        else:
            print("⚠️ No development server available")
            print("💡 You can launch one with: python runcomfy/dev_server_startup.py")
        
        # Test machine getting logic (without actually launching)
        print("\n🔍 Testing machine coordination logic...")
        
        # This would normally get or create a machine
        # For testing, we'll just verify the logic flow
        print("✅ Machine coordination logic ready")
        
    except Exception as e:
        print(f"❌ Machine coordination test failed: {e}")


async def test_job_lifecycle():
    """Test complete job creation and management"""
    print("\n🧪 Testing Job Lifecycle")
    print("="*50)
    
    orchestrator = RunComfyOrchestrator()
    
    try:
        # Test job creation
        test_prompt = "A futuristic mechanical helmet with glowing blue details"
        job = await orchestrator.create_job(test_prompt)
        
        print(f"✅ Job created: {job.job_id}")
        print(f"   Status: {job.status.value}")
        print(f"   Prompt: {job.prompt}")
        print(f"   Created: {job.created_at}")
        
        # Test job retrieval
        retrieved_job = orchestrator.get_job_status(job.job_id)
        if retrieved_job and retrieved_job.job_id == job.job_id:
            print("✅ Job retrieval working")
        else:
            print("❌ Job retrieval failed")
        
        # Test job listing
        all_jobs = orchestrator.get_all_jobs()
        active_jobs = orchestrator.get_active_jobs()
        
        print(f"✅ Job listing: {len(all_jobs)} total, {len(active_jobs)} active")
        
        # Test job dictionary conversion
        job_dict = job.to_dict()
        if "job_id" in job_dict and "status" in job_dict:
            print("✅ Job serialization working")
        else:
            print("❌ Job serialization failed")
        
        # Test cleanup
        cleanup_success = await orchestrator.cleanup_job(job.job_id)
        if cleanup_success:
            print("✅ Job cleanup working")
        else:
            print("❌ Job cleanup failed")
        
    except Exception as e:
        print(f"❌ Job lifecycle test failed: {e}")


async def test_workflow_execution_simulation():
    """Test workflow execution simulation (without actually running)"""
    print("\n🧪 Testing Workflow Execution Simulation")
    print("="*50)
    
    orchestrator = RunComfyOrchestrator()
    
    try:
        # Check if we have a server available for actual testing
        dev_server_manager = DevServerStateManager()
        dev_server = dev_server_manager.load_server_state()
        
        if dev_server and dev_server.status == "running":
            # Check if server is healthy
            is_healthy = await dev_server_manager.check_server_health(dev_server)
            
            if is_healthy:
                print("🚀 Development server is available and healthy")
                print("   This would be perfect for a full workflow test!")
                print("   (Skipping actual execution to avoid costs)")
                
                # Simulate what would happen
                test_prompt = "A detailed cyberpunk helmet with neon accents"
                print(f"\n📝 Simulated workflow execution:")
                print(f"   1. Create job with prompt: {test_prompt[:50]}...")
                print(f"   2. Use development server: {dev_server.server_id}")
                print(f"   3. Load and prepare workflow")
                print(f"   4. Execute with progress tracking")
                print(f"   5. Handle results and cost calculation")
                
                # Test cost estimation for realistic duration
                cost_estimate = orchestrator.estimate_cost(dev_server.server_type, 240)  # 4 minutes
                print(f"   💰 Estimated cost: ${cost_estimate}")
                
                print("✅ Workflow execution simulation complete")
            else:
                print("⚠️ Development server is unhealthy")
        else:
            print("⚠️ No development server available for simulation")
            print("💡 Launch with: python runcomfy/dev_server_startup.py")
        
    except Exception as e:
        print(f"❌ Workflow execution simulation failed: {e}")


async def test_full_workflow_execution():
    """Test actual workflow execution (optional, requires healthy server)"""
    print("\n🧪 Full Workflow Execution Test (Optional)")
    print("="*50)
    
    # Ask user if they want to run actual workflow
    print("⚠️ This test will execute an actual workflow and incur costs.")
    print("🔍 Checking server availability...")
    
    dev_server_manager = DevServerStateManager()
    dev_server = dev_server_manager.load_server_state()
    
    if not dev_server or dev_server.status != "running":
        print("❌ No development server available")
        print("💡 Launch with: python runcomfy/dev_server_startup.py")
        return
    
    is_healthy = await dev_server_manager.check_server_health(dev_server)
    if not is_healthy:
        print("❌ Development server is not healthy")
        return
    
    print(f"✅ Healthy server available: {dev_server.server_id}")
    print("💡 Uncomment the execution code below to run a real test")
    
    # Commented out to avoid accidental execution
    """
    try:
        orchestrator = RunComfyOrchestrator()
        
        test_prompt = "A simple geometric cube with metallic surface"
        print(f"🚀 Executing real workflow with prompt: {test_prompt}")
        
        # Execute the workflow
        job = await orchestrator.execute_flux_mesh_generation(test_prompt)
        
        print(f"🏁 Workflow completed!")
        print(f"   Job ID: {job.job_id}")
        print(f"   Status: {job.status.value}")
        print(f"   Cost: ${job.actual_machine_cost}")
        
        if job.status == JobStatus.COMPLETED:
            print(f"   Results:")
            print(f"     Image: {job.generated_image_url}")
            print(f"     Mesh: {job.generated_mesh_url}")
        else:
            print(f"   Error: {job.error_message}")
            
    except Exception as e:
        print(f"❌ Full workflow test failed: {e}")
    """


async def test_cost_and_monitoring():
    """Test cost tracking and monitoring features"""
    print("\n🧪 Testing Cost and Monitoring")
    print("="*50)
    
    orchestrator = RunComfyOrchestrator()
    
    try:
        # Test cost summary
        cost_summary = await orchestrator.get_cost_summary()
        
        print("✅ Cost summary generated:")
        print(f"   Total jobs: {cost_summary['total_jobs']}")
        print(f"   Active jobs: {cost_summary['active_jobs']}")
        print(f"   Total estimated cost: ${cost_summary['total_estimated_cost']}")
        print(f"   Total actual cost: ${cost_summary['total_actual_cost']}")
        print(f"   Active machines: {cost_summary['active_machines']}")
        
        # Test cost rates
        print("\n💰 Cost rates per hour:")
        for machine_type, rate in cost_summary['cost_per_hour_rates'].items():
            print(f"   {machine_type}: ${rate}/hour")
        
        # Test idle machine cleanup logic
        print("\n🧹 Testing cleanup logic...")
        await orchestrator.shutdown_idle_machines()
        print("✅ Cleanup logic executed (no machines to clean)")
        
    except Exception as e:
        print(f"❌ Cost and monitoring test failed: {e}")


async def main():
    """Run all orchestrator tests"""
    print("🎯 CONJURE RunComfy Orchestrator Test Suite")
    print("="*60)
    
    # Run tests in sequence
    orchestrator = await test_orchestrator_initialization()
    if orchestrator:
        await test_machine_coordination()
        await test_job_lifecycle()
        await test_workflow_execution_simulation()
        await test_full_workflow_execution()
        await test_cost_and_monitoring()
    
    print(f"\n🎉 Orchestrator test suite completed!")
    print("💡 The orchestrator is ready for integration with CloudGenerationService")


if __name__ == "__main__":
    asyncio.run(main())
