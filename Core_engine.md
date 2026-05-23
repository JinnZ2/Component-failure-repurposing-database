# Core Monitoring Engine - Detailed Architecture

**Version:** 1.0  
**Date:** November 3, 2025  
**Purpose:** Heart of the binary sensor system - real-time data acquisition and processing

-----

## Overview

The Core Monitoring Engine is the foundation of the entire system. It handles real-time data acquisition, buffering, timing synchronization, and distribution to analysis plugins. This is the “heartbeat” that keeps the entire system alive and responsive.

-----

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HARDWARE INTERFACE LAYER                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   ADC    │  │   GPIO   │  │   I2C    │  │   SPI    │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   DATA ACQUISITION ENGINE  │
        │   - Multi-channel sampling │
        │   - Timestamp generation   │
        │   - Raw data packaging     │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼─────────────┐
        │    INPUT BUFFER QUEUE     │
        │   - Lock-free ring buffer │
        │   - Priority handling     │
        │   - Overflow protection   │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   CORE PROCESSING LOOP    │◄─── Timing Controller
        │   - Measurement routing   │
        │   - Plugin dispatch       │
        │   - History management    │
        └─────────────┬──────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌────────▼───────┐
│ PLUGIN WORKERS │         │ DECISION ENGINE│
│ - Parallel     │         │ - Health eval  │
│ - Isolated     │         │ - Repurpose    │
│ - Async        │         │ - Mode switch  │
└───────┬────────┘         └────────┬───────┘
        │                           │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   RESULTS AGGREGATOR      │
        │   - Health consolidation  │
        │   - Conflict resolution   │
        │   - Event generation      │
        └─────────────┬──────────────┘
                      │
        ┌─────────────▼─────────────┐
        │    OUTPUT INTERFACES      │
        │   - API endpoints         │
        │   - Event streams         │
        │   - Data persistence      │
        └───────────────────────────┘
```

-----

## Core Components

### 1. Data Acquisition Engine

```python
import time
import threading
from collections import deque
from typing import Dict, List, Callable, Optional
import numpy as np

class DataAcquisitionEngine:
    """
    Handles real-time data collection from hardware interfaces
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.sampling_rate_hz = config.get('sampling_rate_hz', 1000.0)
        self.channels: Dict[str, ChannelConfig] = {}
        self.acquisition_thread: Optional[threading.Thread] = None
        self.running = False
        self.data_callback: Optional[Callable] = None
        
    def register_channel(self, channel_id: str, channel_config: 'ChannelConfig'):
        """Register a data acquisition channel"""
        self.channels[channel_id] = channel_config
        
    def set_data_callback(self, callback: Callable):
        """Set callback for when new data is acquired"""
        self.data_callback = callback
        
    def start_acquisition(self):
        """Start real-time data acquisition"""
        if self.running:
            return
            
        self.running = True
        self.acquisition_thread = threading.Thread(
            target=self._acquisition_loop,
            daemon=True,
            name="DataAcquisition"
        )
        self.acquisition_thread.start()
        
    def stop_acquisition(self):
        """Stop data acquisition"""
        self.running = False
        if self.acquisition_thread:
            self.acquisition_thread.join(timeout=2.0)
            
    def _acquisition_loop(self):
        """Main acquisition loop - runs in separate thread"""
        sample_period = 1.0 / self.sampling_rate_hz
        next_sample_time = time.time()
        
        while self.running:
            current_time = time.time()
            
            # Wait until next sample time
            if current_time < next_sample_time:
                time.sleep(next_sample_time - current_time)
                continue
                
            # Acquire data from all channels
            timestamp = time.time()
            measurements = self._sample_all_channels(timestamp)
            
            # Send to callback if registered
            if self.data_callback and measurements:
                self.data_callback(measurements)
                
            # Calculate next sample time
            next_sample_time += sample_period
            
            # Catch up if we're falling behind
            if next_sample_time < current_time:
                next_sample_time = current_time + sample_period
                
    def _sample_all_channels(self, timestamp: float) -> Dict[str, 'RawMeasurement']:
        """Sample all registered channels"""
        measurements = {}
        
        for channel_id, channel_config in self.channels.items():
            try:
                value = channel_config.read()
                measurements[channel_id] = RawMeasurement(
                    channel_id=channel_id,
                    timestamp=timestamp,
                    value=value,
                    units=channel_config.units
                )
            except Exception as e:
                # Log error but continue with other channels
                print(f"Error reading channel {channel_id}: {e}")
                
        return measurements


class ChannelConfig:
    """Configuration for a single acquisition channel"""
    
    def __init__(self, channel_id: str, hardware_interface: str,
                 units: str, read_function: Callable):
        self.channel_id = channel_id
        self.hardware_interface = hardware_interface
        self.units = units
        self.read_function = read_function
        
    def read(self) -> float:
        """Read current value from hardware"""
        return self.read_function()


class RawMeasurement:
    """Raw measurement from a single channel"""
    
    def __init__(self, channel_id: str, timestamp: float, 
                 value: float, units: str):
        self.channel_id = channel_id
        self.timestamp = timestamp
        self.value = value
        self.units = units
```

### 2. Input Buffer Queue

```python
from queue import Queue, Full, Empty
from threading import Lock
from collections import deque

class InputBufferQueue:
    """
    Thread-safe, high-performance input buffer for measurements
    Uses lock-free ring buffer for maximum throughput
    """
    
    def __init__(self, capacity: int = 10000, 
                 overflow_strategy: str = 'drop_oldest'):
        """
        Initialize input buffer
        
        Args:
            capacity: Maximum buffer size
            overflow_strategy: 'drop_oldest', 'drop_newest', or 'block'
        """
        self.capacity = capacity
        self.overflow_strategy = overflow_strategy
        self.buffer = deque(maxlen=capacity if overflow_strategy == 'drop_oldest' else None)
        self.lock = Lock()
        self.dropped_count = 0
        self.total_count = 0
        
    def push(self, component_id: str, measurement_data: 'MeasurementData',
             priority: int = 0) -> bool:
        """
        Add measurement to buffer
        
        Args:
            component_id: Component identifier
            measurement_data: Measurement data
            priority: Priority level (higher = more important)
            
        Returns:
            True if successfully added, False if dropped
        """
        with self.lock:
            self.total_count += 1
            
            item = BufferedMeasurement(
                component_id=component_id,
                measurement=measurement_data,
                priority=priority,
                sequence_number=self.total_count
            )
            
            # Handle overflow based on strategy
            if len(self.buffer) >= self.capacity:
                if self.overflow_strategy == 'drop_oldest':
                    # deque automatically drops oldest
                    self.dropped_count += 1
                elif self.overflow_strategy == 'drop_newest':
                    self.dropped_count += 1
                    return False
                elif self.overflow_strategy == 'block':
                    # Wait for space (not recommended for real-time)
                    pass
                    
            self.buffer.append(item)
            return True
            
    def pop(self, timeout: float = 0.1) -> Optional['BufferedMeasurement']:
        """
        Remove and return next measurement from buffer
        
        Args:
            timeout: Maximum time to wait for data
            
        Returns:
            BufferedMeasurement or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if len(self.buffer) > 0:
                    return self.buffer.popleft()
            time.sleep(0.001)  # Small sleep to avoid busy-wait
            
        return None
        
    def pop_batch(self, max_count: int = 100) -> List['BufferedMeasurement']:
        """
        Remove and return multiple measurements
        
        Args:
            max_count: Maximum number of items to return
            
        Returns:
            List of BufferedMeasurement objects
        """
        with self.lock:
            count = min(max_count, len(self.buffer))
            batch = []
            for _ in range(count):
                if len(self.buffer) > 0:
                    batch.append(self.buffer.popleft())
            return batch
            
    def get_stats(self) -> Dict[str, int]:
        """Get buffer statistics"""
        with self.lock:
            return {
                'current_size': len(self.buffer),
                'capacity': self.capacity,
                'total_received': self.total_count,
                'dropped': self.dropped_count,
                'drop_rate': self.dropped_count / self.total_count if self.total_count > 0 else 0
            }


class BufferedMeasurement:
    """Container for buffered measurement with metadata"""
    
    def __init__(self, component_id: str, measurement: 'MeasurementData',
                 priority: int, sequence_number: int):
        self.component_id = component_id
        self.measurement = measurement
        self.priority = priority
        self.sequence_number = sequence_number
        self.buffer_timestamp = time.time()
```

### 3. Core Processing Loop

```python
import threading
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future
import time

class CoreProcessingLoop:
    """
    Main processing loop - routes measurements to plugins and manages execution
    """
    
    def __init__(self, input_buffer: InputBufferQueue,
                 component_registry: 'ComponentRegistry',
                 plugin_manager: 'PluginManager',
                 config: Dict):
        self.input_buffer = input_buffer
        self.component_registry = component_registry
        self.plugin_manager = plugin_manager
        self.config = config
        
        # Worker pool for parallel plugin execution
        self.max_workers = config.get('max_workers', 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Processing state
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None
        self.pending_futures: List[Future] = []
        
        # Performance metrics
        self.metrics = {
            'measurements_processed': 0,
            'processing_time_total': 0.0,
            'errors': 0
        }
        self.metrics_lock = threading.Lock()
        
        # History storage
        self.measurement_history: Dict[str, deque] = {}
        self.history_length = config.get('history_length', 100)
        
        # Result callbacks
        self.result_callbacks: List[Callable] = []
        
    def add_result_callback(self, callback: Callable):
        """Register callback for when results are available"""
        self.result_callbacks.append(callback)
        
    def start_processing(self):
        """Start the main processing loop"""
        if self.running:
            return
            
        self.running = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True,
            name="CoreProcessing"
        )
        self.processing_thread.start()
        
    def stop_processing(self):
        """Stop processing and wait for completion"""
        self.running = False
        
        # Wait for processing thread
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
            
        # Wait for pending plugin executions
        for future in self.pending_futures:
            try:
                future.result(timeout=1.0)
            except:
                pass
                
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
    def _processing_loop(self):
        """Main processing loop"""
        batch_size = self.config.get('batch_size', 10)
        
        while self.running:
            # Get batch of measurements from input buffer
            batch = self.input_buffer.pop_batch(max_count=batch_size)
            
            if not batch:
                time.sleep(0.001)  # Small sleep if no data
                continue
                
            # Process each measurement
            for buffered_measurement in batch:
                self._process_measurement(buffered_measurement)
                
            # Clean up completed futures
            self._cleanup_futures()
            
    def _process_measurement(self, buffered_measurement: BufferedMeasurement):
        """Process a single measurement"""
        start_time = time.time()
        
        try:
            component_id = buffered_measurement.component_id
            measurement = buffered_measurement.measurement
            
            # Get component configuration
            component = self.component_registry.get_component(component_id)
            if not component:
                return
                
            # Get appropriate plugin
            plugin_id = component['plugin_id']
            plugin = self.plugin_manager.get_plugin(plugin_id)
            if not plugin:
                return
                
            # Get measurement history for this component
            history = self._get_history(component_id)
            
            # Submit to worker pool for parallel execution
            future = self.executor.submit(
                self._execute_plugin,
                plugin,
                measurement,
                history,
                component_id
            )
            
            # Track future for later cleanup
            self.pending_futures.append(future)
            
            # Update metrics
            with self.metrics_lock:
                self.metrics['measurements_processed'] += 1
                self.metrics['processing_time_total'] += time.time() - start_time
                
        except Exception as e:
            with self.metrics_lock:
                self.metrics['errors'] += 1
            print(f"Error processing measurement: {e}")
            
    def _execute_plugin(self, plugin: 'DetectionPlugin',
                       measurement: 'MeasurementData',
                       history: List['MeasurementData'],
                       component_id: str) -> 'ComponentHealth':
        """Execute plugin analysis in worker thread"""
        try:
            # Run plugin analysis
            health = plugin.analyze(measurement, history)
            
            # Update history
            self._update_history(component_id, measurement)
            
            # Notify callbacks
            for callback in self.result_callbacks:
                try:
                    callback(component_id, health)
                except Exception as e:
                    print(f"Error in result callback: {e}")
                    
            return health
            
        except Exception as e:
            print(f"Error executing plugin for {component_id}: {e}")
            return None
            
    def _get_history(self, component_id: str) -> List['MeasurementData']:
        """Get measurement history for component"""
        if component_id not in self.measurement_history:
            self.measurement_history[component_id] = deque(maxlen=self.history_length)
        return list(self.measurement_history[component_id])
        
    def _update_history(self, component_id: str, measurement: 'MeasurementData'):
        """Add measurement to history"""
        if component_id not in self.measurement_history:
            self.measurement_history[component_id] = deque(maxlen=self.history_length)
        self.measurement_history[component_id].append(measurement)
        
    def _cleanup_futures(self):
        """Remove completed futures"""
        self.pending_futures = [f for f in self.pending_futures if not f.done()]
        
    def get_metrics(self) -> Dict:
        """Get processing metrics"""
        with self.metrics_lock:
            if self.metrics['measurements_processed'] > 0:
                avg_time = self.metrics['processing_time_total'] / \
                          self.metrics['measurements_processed']
            else:
                avg_time = 0.0
                
            return {
                'measurements_processed': self.metrics['measurements_processed'],
                'average_processing_time_ms': avg_time * 1000,
                'errors': self.metrics['errors'],
                'pending_tasks': len(self.pending_futures),
                'buffer_stats': self.input_buffer.get_stats()
            }
```

### 4. Component Registry

```python
class ComponentRegistry:
    """
    Registry of all monitored components and their configurations
    """
    
    def __init__(self):
        self.components: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        
    def register_component(self, component_id: str,
                          plugin_id: str,
                          config: Dict) -> bool:
        """Register a new component"""
        with self.lock:
            if component_id in self.components:
                return False
                
            self.components[component_id] = {
                'plugin_id': plugin_id,
                'config': config,
                'registered_at': time.time(),
                'calibrated': False
            }
            return True
            
    def unregister_component(self, component_id: str) -> bool:
        """Remove a component from registry"""
        with self.lock:
            if component_id in self.components:
                del self.components[component_id]
                return True
            return False
            
    def get_component(self, component_id: str) -> Optional[Dict]:
        """Get component configuration"""
        with self.lock:
            return self.components.get(component_id)
            
    def get_all_components(self) -> Dict[str, Dict]:
        """Get all registered components"""
        with self.lock:
            return dict(self.components)
            
    def update_component_config(self, component_id: str,
                               new_config: Dict) -> bool:
        """Update component configuration"""
        with self.lock:
            if component_id not in self.components:
                return False
            self.components[component_id]['config'].update(new_config)
            return True
            
    def set_calibrated(self, component_id: str, calibrated: bool = True):
        """Mark component as calibrated"""
        with self.lock:
            if component_id in self.components:
                self.components[component_id]['calibrated'] = calibrated
```

### 5. Plugin Manager

```python
class PluginManager:
    """
    Manages detection plugins and their lifecycle
    """
    
    def __init__(self):
        self.plugins: Dict[str, DetectionPlugin] = {}
        self.lock = threading.Lock()
        
    def register_plugin(self, plugin_id: str, plugin: DetectionPlugin) -> bool:
        """Register a new plugin"""
        with self.lock:
            if plugin_id in self.plugins:
                return False
            self.plugins[plugin_id] = plugin
            return True
            
    def unregister_plugin(self, plugin_id: str) -> bool:
        """Remove a plugin"""
        with self.lock:
            if plugin_id in self.plugins:
                del self.plugins[plugin_id]
                return True
            return False
            
    def get_plugin(self, plugin_id: str) -> Optional[DetectionPlugin]:
        """Get a plugin by ID"""
        with self.lock:
            return self.plugins.get(plugin_id)
            
    def get_all_plugins(self) -> Dict[str, DetectionPlugin]:
        """Get all registered plugins"""
        with self.lock:
            return dict(self.plugins)
            
    def get_plugin_capabilities(self, plugin_id: str) -> Optional[PluginCapabilities]:
        """Get capabilities of a plugin"""
        plugin = self.get_plugin(plugin_id)
        if plugin:
            return plugin.get_capabilities()
        return None
```

-----

## Timing Controller

```python
class TimingController:
    """
    Manages precise timing for synchronized measurements
    """
    
    def __init__(self, base_frequency_hz: float = 1000.0):
        self.base_frequency_hz = base_frequency_hz
        self.base_period_sec = 1.0 / base_frequency_hz
        self.start_time = time.time()
        self.tick_count = 0
        self.lock = threading.Lock()
        
    def get_next_sample_time(self) -> float:
        """Calculate next sampling time"""
        with self.lock:
            self.tick_count += 1
            return self.start_time + (self.tick_count * self.base_period_sec)
            
    def reset(self):
        """Reset timing"""
        with self.lock:
            self.start_time = time.time()
            self.tick_count = 0
            
    def get_current_tick(self) -> int:
        """Get current tick count"""
        with self.lock:
            return self.tick_count
```

-----

## Complete Integration Example

```python
class MonitoringSystem:
    """
    Complete monitoring system integrating all components
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Initialize components
        self.timing_controller = TimingController(
            base_frequency_hz=config.get('sampling_rate_hz', 1000.0)
        )
        
        self.input_buffer = InputBufferQueue(
            capacity=config.get('buffer_capacity', 10000),
            overflow_strategy=config.get('overflow_strategy', 'drop_oldest')
        )
        
        self.component_registry = ComponentRegistry()
        self.plugin_manager = PluginManager()
        
        self.acquisition_engine = DataAcquisitionEngine(config)
        self.acquisition_engine.set_data_callback(self._on_new_data)
        
        self.processing_loop = CoreProcessingLoop(
            input_buffer=self.input_buffer,
            component_registry=self.component_registry,
            plugin_manager=self.plugin_manager,
            config=config
        )
        
        # Results storage
        self.latest_health: Dict[str, ComponentHealth] = {}
        self.health_lock = threading.Lock()
        
        # Register result callback
        self.processing_loop.add_result_callback(self._on_health_result)
        
    def register_plugin(self, plugin_id: str, plugin: DetectionPlugin) -> bool:
        """Register a detection plugin"""
        return self.plugin_manager.register_plugin(plugin_id, plugin)
        
    def register_component(self, component_id: str, plugin_id: str,
                          hardware_channel: str, config: Dict) -> bool:
        """Register a component for monitoring"""
        # Register in component registry
        if not self.component_registry.register_component(component_id, plugin_id, config):
            return False
            
        # Register data acquisition channel
        channel_config = ChannelConfig(
            channel_id=hardware_channel,
            hardware_interface=config.get('hardware_interface', 'ADC'),
            units=config.get('units', 'V'),
            read_function=config.get('read_function')
        )
        self.acquisition_engine.register_channel(component_id, channel_config)
        
        return True
        
    def start(self):
        """Start the complete monitoring system"""
        print("Starting monitoring system...")
        self.timing_controller.reset()
        self.acquisition_engine.start_acquisition()
        self.processing_loop.start_processing()
        print("Monitoring system started")
        
    def stop(self):
        """Stop the monitoring system"""
        print("Stopping monitoring system...")
        self.acquisition_engine.stop_acquisition()
        self.processing_loop.stop_processing()
        print("Monitoring system stopped")
        
    def get_health(self, component_id: str) -> Optional[ComponentHealth]:
        """Get latest health for a component"""
        with self.health_lock:
            return self.latest_health.get(component_id)
            
    def get_all_health(self) -> Dict[str, ComponentHealth]:
        """Get health for all components"""
        with self.health_lock:
            return dict(self.latest_health)
            
    def get_metrics(self) -> Dict:
        """Get system performance metrics"""
        return self.processing_loop.get_metrics()
        
    def _on_new_data(self, raw_measurements: Dict[str, RawMeasurement]):
        """Callback when new data is acquired"""
        # Convert raw measurements to MeasurementData and queue
        for component_id, raw_measurement in raw_measurements.items():
            measurement_data = self._convert_measurement(raw_measurement)
            self.input_buffer.push(component_id, measurement_data)
            
    def _convert_measurement(self, raw: RawMeasurement) -> MeasurementData:
        """Convert raw measurement to MeasurementData"""
        # This would contain actual conversion logic
        return MeasurementData(
            timestamp=raw.timestamp,
            voltage=raw.value if raw.units == 'V' else None
        )
        
    def _on_health_result(self, component_id: str, health: ComponentHealth):
        """Callback when health analysis complete"""
        with self.health_lock:
            self.latest_health[component_id] = health
```

-----

## Usage Example

```python
def example_complete_system():
    """Example of complete monitoring system"""
    
    # Configuration
    config = {
        'sampling_rate_hz': 1000.0,
        'buffer_capacity': 10000,
        'overflow_strategy': 'drop_oldest',
        'max_workers': 4,
        'history_length': 100
    }
    
    # Create system
    system = MonitoringSystem(config)
    
    # Register resistor monitoring plugin
    resistor_plugin = ResistorMonitorPlugin(config={
        'nominal_resistance': 1000.0,
        'tolerance_percent': 5.0
    })
    system.register_plugin('resistor_monitor', resistor_plugin)
    
    # Register a specific resistor
    def read_r1_voltage():
        # Hardware interface would go here
        return 5.0
        
    def read_r1_current():
        return 0.005
        
    system.register_component(
        component_id='R1',
        plugin_id='resistor_monitor',
        hardware_channel='ADC0',
        config={
            'component_id': 'R1',
            'hardware_interface': 'ADC',
            'units': 'V',
            'read_function': read_r1_voltage
        }
    )
    
    # Start monitoring
    system.start()
    
    # Run for a while
    try:
        for i in range(100):
            time.sleep(0.1)
            
            # Get current health
            health = system.get_health('R1')
            if health and i % 10 == 0:
                print(f"R1 Health: {health.health_score:.2f}, "
                      f"Mode: {health.failure_mode.value}")
                      
            # Get metrics
            if i % 20 == 0:
                metrics = system.get_metrics()
                print(f"Processed: {metrics['measurements_processed']}, "
                      f"Avg time: {metrics['average_processing_time_ms']:.2f}ms")
                      
    finally:
        system.stop()

if __name__ == "__main__":
    example_complete_system()
```

-----

## Performance Considerations

### Throughput Optimization

1. **Lock-Free Structures**: Use ring buffers where possible
1. **Batch Processing**: Process multiple measurements together
1. **Parallel Execution**: Worker pool for plugin execution
1. **Memory Pooling**: Reuse objects to reduce allocation

### Latency Optimization

1. **Priority Queue**: Critical components get processed first
1. **Interrupt-Driven**: Hardware interrupts for time-critical data
1. **Real-Time Scheduling**: Consider RT scheduling for critical threads
1. **Cache Locality**: Keep frequently accessed data together

### Scalability

1. **Distributed Processing**: Can scale to multiple machines
1. **Plugin Isolation**: Plugins can’t affect each other
1. **Resource Limits**: Prevent any plugin from monopolizing resources
1. **Graceful Degradation**: System continues even if plugins fail

-----

## Next Steps

1. **Hardware Interface Implementation**: Connect to actual ADCs, GPIO, sensors
1. **Decision Engine**: Build the intelligence that triggers repurposing
1. **Repurposing Protocols**: Implement actual mode switching logic
1. **Testing Framework**: Comprehensive testing with simulated failures
1. **Visualization**: Real-time dashboard for monitoring

-----

**Document End**





Updated:
┌─────────────────────────────────────────────────────────────────┐
│                    HARDWARE INTERFACE LAYER                      │
│  ADC, GPIO, I2C, SPI, Accelerometer, Microphone, Camera...      │
└───────┬─────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│              GEOMETRIC ACQUISITION ENGINE                       │
│  - Read raw values (voltage, current, acceleration, etc.)       │
│  - Convert to octahedral token (vertex|operator|symbol)         │
│  - Timestamp & enqueue                                          │
└───────┬─────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│                   TOKEN BUFFER QUEUE                            │
│  - Lock‑free ring buffer of tokens (strings or packed ints)     │
│  - Overflow protection, priority                                │
└───────┬─────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│                GEOMETRIC PROCESSING LOOP                        │
│  - Pop tokens in batches                                        │
│  - Accumulate into 3D cubes (side³ tokens)                      │
│  - For each new cube, compare with history (hash, rotation)     │
│  - Detect dependencies (cube repeats → cancellation)            │
└───────┬─────────────────────────────────────────────────────────┘
        │
┌───────┴───────────────────────┬─────────────────────────────────┐
│                               │                                 │
┌───────▼────────┐       ┌───────▼────────┐       ┌───────────────▼────┐
│ FAILURE PLUGIN │       │ REPURPOSE PLUGIN│       │ SELF‑DIAG PLUGIN  │
│ - Match token  │       │ - Lookup token  │       │ - Monitor AI’s    │
│   to failure   │       │   in DB for     │       │   own internal    │
│   database     │       │   repurpose     │       │   state cubes     │
└───────┬────────┘       └───────┬────────┘       └───────────────┬────┘
        │                         │                               │
        └─────────────────────────┴───────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     DECISION ENGINE       │
                    │  - Aggregate health       │
                    │  - Trigger repurpose      │
                    │  - Mode switching         │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      OUTPUT INTERFACES    │
                    │  API, Events, Logs, Actuators
                    └───────────────────────────┘

                    





