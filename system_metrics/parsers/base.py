"""
Base interfaces for system data parsers.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar

# Define a generic type for parsed data
T = TypeVar('T')


class DataParser(Generic[T], ABC):
    """
    Abstract base class for data parsers.
    
    Parsers are responsible for converting raw data from providers
    into structured, typed data that can be used by higher-level
    components.
    """
    
    @abstractmethod
    def parse(self, raw_data: Dict[str, Any]) -> T:
        """
        Parse raw data into a structured format.
        
        Args:
            raw_data: Dictionary containing raw data from a provider.
            
        Returns:
            Structured data in the format defined by the parser implementation.
            
        Raises:
            ValueError: If the raw data cannot be parsed.
        """
        pass
