"""
Real-time metrics update system for the macOS monitoring application.

This module provides an event-driven architecture for real-time UI updates
without blocking the main application thread.
"""
import time
import weakref
import threading
import queue
from typing import Dict, List, Any, Callable, Set, Optional, TypeVar, Generic, Tuple
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime


# Type variables for generic observer typing
T = TypeVar('T')


class MetricUpdateEvent(Enum):
    """Types of metric update events."""
    
    # General events
    METRICS_UPDATED = auto()
    COLLECTION_ERROR = auto()
    
    # Specific metric groups
    CPU_OVERALL_UPDATED = auto()
    CPU_CORES_UPDATED = auto()
    CPU_PROCESSES_UPDATED = auto()
    MEMORY_UPDATED = auto()
    DISK_UPDATED = auto()
    
    # Performance-related events
    PERFORMANCE_ALERT = auto()
    THRESHOLD_EXCEEDED = auto()


@dataclass
class MetricEvent:
    """Event data for metric updates."""
    
    event_type: MetricUpdateEvent
    timestamp: float
    source: str
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    
    def __post_init__(self):
        """Set default timestamp if not provided."""
        if not hasattr(self, 'timestamp') or self.timestamp is None:
            self.timestamp = time.time()
    
    @property
    def age(self) -> float:
        """Get the age of this event in seconds."""
        return time.time() - self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to a dictionary."""
        return {
            "event_type": self.event_type.name,
            "timestamp": self.timestamp,
            "source": self.source,
            "data": self.data,
            "message": self.message
        }


class Observer(Generic[T]):
    """
    Generic observer interface for the observer pattern.
    
    This abstract class defines the interface for objects that wish to receive
    notifications about events.
    """
    
    def update(self, event: T) -> None:
        """
        Receive an update notification.
        
        Args:
            event: The event data
        """
        raise NotImplementedError("Observer subclasses must implement update()")


class Subject(Generic[T]):
    """
    Generic subject interface for the observer pattern.
    
    This abstract class defines the interface for objects that generate events
    and notify observers.
    """
    
    def __init__(self):
        """Initialize the subject with an empty observer set."""
        self._observers: Set[weakref.ReferenceType] = set()
    
    def attach(self, observer: Observer[T]) -> None:
        """
        Attach an observer to this subject.
        
        Args:
            observer: The observer to attach
        """
        self._observers.add(weakref.ref(observer))
    
    def detach(self, observer: Observer[T]) -> None:
        """
        Detach an observer from this subject.
        
        Args:
            observer: The observer to detach
        """
        observer_ref = None
        for ref in self._observers:
            if ref() is observer:
                observer_ref = ref
                break
                
        if observer_ref:
            self._observers.remove(observer_ref)
    
    def notify(self, event: T) -> None:
        """
        Notify all observers about an event.
        
        Args:
            event: The event data to send to observers
        """
        dead_refs = set()
        for observer_ref in self._observers:
            observer = observer_ref()
            if observer is not None:
                observer.update(event)
            else:
                dead_refs.add(observer_ref)
        
        # Clean up dead references
        self._observers -= dead_refs


class MetricsEventDispatcher(Subject[MetricEvent]):
    """
    Central event dispatcher for metrics updates.
    
    This class manages the distribution of metric events to interested observers
    using a thread-safe design to prevent blocking the main thread.
    """
    
    _instance = None
    
    def __new__(cls):
        """Ensure only one dispatcher exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(MetricsEventDispatcher, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the dispatcher if not already initialized."""
        if not hasattr(self, '_initialized') or not self._initialized:
            super().__init__()
            self._event_queue = queue.Queue()
            self._running = False
            self._dispatch_thread = None
            self._event_filters: Dict[weakref.ReferenceType, Set[MetricUpdateEvent]] = {}
            self._initialized = True
    
    def start(self) -> None:
        """Start the event dispatch thread."""
        if self._running:
            return
            
        self._running = True
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop, 
            daemon=True,
            name="MetricsEventDispatcher"
        )
        self._dispatch_thread.start()
    
    def stop(self) -> None:
        """Stop the event dispatch thread."""
        self._running = False
        if self._dispatch_thread:
            # Add a sentinel value to unblock the queue
            self._event_queue.put(None)
            self._dispatch_thread.join(timeout=1.0)
            self._dispatch_thread = None
    
    def attach_with_filter(self, observer: Observer[MetricEvent], event_types: List[MetricUpdateEvent]) -> None:
        """
        Attach an observer with event type filtering.
        
        Args:
            observer: The observer to attach
            event_types: List of event types the observer is interested in
        """
        self.attach(observer)
        observer_ref = None
        for ref in self._observers:
            if ref() is observer:
                observer_ref = ref
                break
                
        if observer_ref:
            self._event_filters[observer_ref] = set(event_types)
    
    def publish_event(self, event: MetricEvent) -> None:
        """
        Publish an event to be dispatched to observers.
        
        Args:
            event: The event to publish
        """
        self._event_queue.put(event)
    
    def _dispatch_loop(self) -> None:
        """Background thread that dispatches events from the queue."""
        while self._running:
            try:
                # Get the next event from the queue
                event = self._event_queue.get(block=True, timeout=0.5)
                if event is None:  # Sentinel for shutdown
                    break
                    
                # Dispatch the event to interested observers
                self._dispatch_event(event)
                
                # Mark task as done
                self._event_queue.task_done()
                
            except queue.Empty:
                # Queue timeout - just continue
                continue
            except Exception as e:
                print(f"Error in event dispatch: {e}")
                # Continue running despite errors
    
    def _dispatch_event(self, event: MetricEvent) -> None:
        """
        Dispatch an event to all interested observers.
        
        Args:
            event: The event to dispatch
        """
        dead_refs = set()
        
        for observer_ref in self._observers:
            # Check if observer still exists
            observer = observer_ref()
            if observer is None:
                dead_refs.add(observer_ref)
                continue
                
            # Apply event filtering if configured for this observer
            if observer_ref in self._event_filters:
                if event.event_type not in self._event_filters[observer_ref]:
                    continue
            
            # Dispatch the event
            try:
                observer.update(event)
            except Exception as e:
                print(f"Error notifying observer {observer}: {e}")
        
        # Clean up dead references
        self._observers -= dead_refs
        for ref in dead_refs:
            if ref in self._event_filters:
                del self._event_filters[ref]
                

class MetricsEventFilter:
    """
    Filter for selectively processing metric events.
    
    This class can be used to filter events based on various criteria.
    """
    
    def __init__(self, event_types: Optional[List[MetricUpdateEvent]] = None):
        """
        Initialize the event filter.
        
        Args:
            event_types: Optional list of event types to accept (None = accept all)
        """
        self.event_types = set(event_types) if event_types else None
    
    def matches(self, event: MetricEvent) -> bool:
        """
        Check if an event matches the filter criteria.
        
        Args:
            event: The event to check
            
        Returns:
            True if the event matches, False otherwise
        """
        # Filter by event type if specified
        if self.event_types is not None and event.event_type not in self.event_types:
            return False
            
        return True
