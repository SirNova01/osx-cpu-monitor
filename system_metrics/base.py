"""
Base classes and interfaces for system metrics collection.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class MetricValue:
    """Represents a single metric value with timestamp."""
    timestamp: datetime
    value: Any
    unit: str = ""
    
    def __str__(self) -> str:
        return f"{self.value}{self.unit}"


class Metric:
    """Base class for all metrics."""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._history: List[MetricValue] = []
        
    def add_value(self, value: Any, unit: str = "") -> None:
        """Add a new value to this metric's history."""
        metric_value = MetricValue(
            timestamp=datetime.now(),
            value=value,
            unit=unit
        )
        self._history.append(metric_value)
    
    @property
    def current_value(self) -> Optional[MetricValue]:
        """Get the most recent value of this metric."""
        if not self._history:
            return None
        return self._history[-1]
    
    @property
    def history(self) -> List[MetricValue]:
        """Get the history of this metric's values."""
        return self._history.copy()
    
    def clear_history(self) -> None:
        """Clear the history of this metric."""
        self._history = []


class MetricsCollector(ABC):
    """Abstract base class for all metrics collectors."""
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
    
    @abstractmethod
    def collect(self) -> Dict[str, Metric]:
        """Collect metrics and update their values."""
        pass
    
    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a metric by name."""
        return self._metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, Metric]:
        """Get all metrics."""
        return self._metrics.copy()


class SystemMetricsCollector:
    """Main class for collecting system metrics."""
    
    def __init__(self):
        self._collectors: List[MetricsCollector] = []
    
    def register_collector(self, collector: MetricsCollector) -> None:
        """Register a new metrics collector."""
        self._collectors.append(collector)
    
    def collect_all(self) -> Dict[str, Dict[str, Metric]]:
        """Collect all metrics from all registered collectors."""
        results = {}
        for collector in self._collectors:
            collector_name = collector.__class__.__name__
            results[collector_name] = collector.collect()
        return results
    
    def get_all_metrics(self) -> Dict[str, Metric]:
        """Get all metrics from all registered collectors."""
        all_metrics = {}
        for collector in self._collectors:
            all_metrics.update(collector.get_all_metrics())
        return all_metrics