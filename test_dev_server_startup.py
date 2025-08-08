"""
Test Development Server Startup functionality

Tests the dev_server_startup.py script and dev_server_state.py functionality
without actually launching real servers (unless --live flag is used).
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from runcomfy.dev_server_state import DevServerStateManager, DevServerState
from runcomfy.dev_server_startup import DevServerManager


class TestDevServerState:
    """Test development server state management"""
    
    def test_save_and_load_state(self):
        """Test saving and loading server state"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            # Create state manager with temp file
            state_manager = DevServerStateManager(temp_path)
            
            # Create test state
            state = DevServerState(
                server_id="test-server-123",
                user_id="test-user-456",
                base_url="https://test.runcomfy.com",
                status="running",
                launch_time="2024-01-01T10:00:00Z",
                workflow_version="test-version",
                server_type="medium",
                total_cost=0.25,
                session_cost=0.15
            )
            
            # Save state
            state_manager.save_server_state(state)
            
            # Load state
            loaded_state = state_manager.load_server_state()
            
            # Verify
            assert loaded_state is not None
            assert loaded_state.server_id == state.server_id
            assert loaded_state.user_id == state.user_id
            assert loaded_state.base_url == state.base_url
            assert loaded_state.status == state.status
            assert loaded_state.total_cost == state.total_cost
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_has_active_server(self):
        """Test checking for active server"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            state_manager = DevServerStateManager(temp_path)
            
            # No state file should return False
            assert not state_manager.has_active_server()
            
            # Create running state
            state = DevServerState(
                server_id="test-server",
                user_id="test-user",
                base_url="https://test.runcomfy.com",
                status="running",
                launch_time="2024-01-01T10:00:00Z",
                workflow_version="test",
                server_type="medium"
            )
            
            state_manager.save_server_state(state)
            assert state_manager.has_active_server()
            
            # Update to stopped state
            state.status = "stopped"
            state_manager.save_server_state(state)
            assert not state_manager.has_active_server()
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_clear_state(self):
        """Test clearing server state"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            state_manager = DevServerStateManager(temp_path)
            
            # Create and save state
            state = DevServerState(
                server_id="test-server",
                user_id="test-user", 
                base_url="https://test.runcomfy.com",
                status="running",
                launch_time="2024-01-01T10:00:00Z",
                workflow_version="test",
                server_type="medium"
            )
            
            state_manager.save_server_state(state)
            assert state_manager.has_active_server()
            
            # Clear state
            state_manager.clear_server_state()
            assert not state_manager.has_active_server()
            assert not Path(temp_path).exists()
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful server health check"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            state_manager = DevServerStateManager(temp_path)
            
            state = DevServerState(
                server_id="test-server",
                user_id="test-user",
                base_url="https://test.runcomfy.com",
                status="running",
                launch_time="2024-01-01T10:00:00Z",
                workflow_version="test",
                server_type="medium"
            )
            
            # Mock successful HTTP response
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                result = await state_manager.check_server_health(state)
                assert result is True
                assert state.health_status == "healthy"
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test failed server health check"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            state_manager = DevServerStateManager(temp_path)
            
            state = DevServerState(
                server_id="test-server",
                user_id="test-user",
                base_url="https://test.runcomfy.com",
                status="running",
                launch_time="2024-01-01T10:00:00Z",
                workflow_version="test",
                server_type="medium"
            )
            
            # Mock failed HTTP response
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                result = await state_manager.check_server_health(state)
                assert result is False
                assert state.health_status == "unhealthy"
                
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestDevServerManager:
    """Test development server manager"""
    
    def test_load_credentials(self):
        """Test loading credentials from file"""
        # Create temporary credentials file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('userID:"test-user-123"\\n')
            f.write('RUNCOMFY_API_TOKEN:"test-token-456"\\n') 
            f.write('version_id: "test-version-789"\\n')
            temp_path = f.name
        
        try:
            # Mock the credentials path
            with patch('runcomfy.dev_server_startup.Path') as mock_path:
                mock_path.return_value.__truediv__.return_value = Path(temp_path)
                mock_path.return_value.parent = Path(__file__).parent / "runcomfy"
                Path(temp_path).exists = lambda: True
                
                manager = DevServerManager()
                
                assert manager.credentials["userID"] == "test-user-123"
                assert manager.credentials["RUNCOMFY_API_TOKEN"] == "test-token-456"
                assert manager.credentials["version_id"] == "test-version-789"
                
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_launch_server_mock(self):
        """Test server launch with mocked RunComfy client"""
        # Create temporary credentials
        credentials = {
            "userID": "test-user",
            "RUNCOMFY_API_TOKEN": "test-token",
            "version_id": "test-version"
        }
        
        with patch('runcomfy.dev_server_startup.DevServerManager._load_credentials') as mock_creds:
            mock_creds.return_value = credentials
            
            manager = DevServerManager()
            
            # Mock the RunComfy client
            mock_machine_info = MagicMock()
            mock_machine_info.server_id = "test-server-123"
            mock_machine_info.user_id = "test-user"
            mock_machine_info.main_service_url = "https://test.runcomfy.com"
            mock_machine_info.current_status = "Ready"
            
            with patch.object(manager, '_get_client') as mock_get_client:
                mock_client = AsyncMock()
                mock_client.launch_machine.return_value = mock_machine_info
                mock_client.wait_for_machine_ready.return_value = mock_machine_info
                mock_get_client.return_value = mock_client
                
                # Mock state manager
                with patch.object(manager.state_manager, 'has_active_server', return_value=False):
                    with patch.object(manager.state_manager, 'save_server_state') as mock_save:
                        with patch.object(manager.state_manager, 'check_server_health', return_value=True):
                            
                            result = await manager.launch_server()
                            
                            assert result is True
                            mock_client.launch_machine.assert_called_once()
                            mock_client.wait_for_machine_ready.assert_called_once()
                            mock_save.assert_called_once()


@pytest.mark.asyncio 
async def test_main_integration():
    """Test main integration without real server launch"""
    # This test verifies the main function structure without real API calls
    
    # Mock sys.argv for testing different commands
    test_cases = [
        ["--status"],
        ["--server-type", "medium", "--duration", "1800"]
    ]
    
    for test_args in test_cases:
        with patch('sys.argv', ['test_dev_server_startup.py'] + test_args):
            with patch('runcomfy.dev_server_startup.DevServerManager') as mock_manager_class:
                mock_manager = AsyncMock()
                mock_manager_class.return_value = mock_manager
                
                # Import and test main function
                from runcomfy.dev_server_startup import main
                
                try:
                    await main()
                except SystemExit:
                    pass  # Expected for successful execution


def test_credentials_validation():
    """Test credential file validation"""
    # Test missing credentials file
    with patch('runcomfy.dev_server_startup.Path') as mock_path:
        mock_path.return_value.__truediv__.return_value.exists.return_value = False
        
        with pytest.raises(FileNotFoundError):
            DevServerManager()


if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running development server tests...")
    
    # Test state management
    print("\\n1. Testing state management...")
    test_state = TestDevServerState()
    test_state.test_save_and_load_state()
    test_state.test_has_active_server()
    test_state.test_clear_state()
    print("✅ State management tests passed")
    
    # Test credentials loading (with mock)
    print("\\n2. Testing credentials loading...")
    test_manager = TestDevServerManager()
    test_manager.test_load_credentials()
    print("✅ Credentials loading tests passed")
    
    print("\\n🎉 All basic tests passed!")
    print("\\nTo run async tests, use: pytest test_dev_server_startup.py")
    print("To test with real servers, use: pytest test_dev_server_startup.py --live")
