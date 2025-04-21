"""
Base interfaces for system data providers.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class SystemDataProvider(ABC):
    """
    Abstract base class for system data providers.
    
    Providers are responsible for making low-level system calls and
    returning raw data in a standardized format. They should not
    process or transform the data beyond what's necessary for
    basic parsing.
    """
    
    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        """
        Retrieve raw system data.
        
        Returns:
            A dictionary containing raw system data.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available on the current system.
        
        Returns:
            True if the provider can be used, False otherwise.
        """
        pass


class CommandExecutionProvider(SystemDataProvider):
    """Base class for providers that execute system commands."""
    
    def execute_command(self, command: str) -> str:
        """
        Execute a system command and return its output.
        
        Args:
            command: The command to execute.
            
        Returns:
            The command's output as a string.
            
        Raises:
            RuntimeError: If the command execution fails.
        """
        import subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Command execution failed: {e}")
