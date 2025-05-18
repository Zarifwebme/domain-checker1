import threading
import time
import logging
import os
import signal
import psutil
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class WorkerGuard:
    """
    Helper class to monitor worker processes and prevent timeouts
    by managing resource usage and extending timeouts when needed.
    """

    def __init__(self, timeout: int = 25, warn_at_memory_percent: float = 70.0):
        self.timeout = timeout  # Default worker timeout (in seconds)
        self.warn_at_memory_percent = warn_at_memory_percent
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self._monitor_thread = None
        self._stop_monitoring = threading.Event()

    def start_monitoring(self):
        """Start the background monitoring thread"""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_tasks,
                daemon=True
            )
            self._monitor_thread.start()
            logger.info("Worker monitoring started")

    def stop_monitoring(self):
        """Stop the background monitoring thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_monitoring.set()
            self._monitor_thread.join(timeout=2.0)
            logger.info("Worker monitoring stopped")

    def register_task(self, task_id: str, timeout: Optional[int] = None) -> None:
        """Register a new task for monitoring"""
        with self.lock:
            self.tasks[task_id] = {
                'start_time': time.time(),
                'timeout': timeout or self.timeout,
                'last_activity': time.time(),
                'warnings_issued': 0
            }

        # Make sure monitoring is running
        self.start_monitoring()

        logger.debug(f"Task {task_id} registered for monitoring")

    def update_task_activity(self, task_id: str) -> None:
        """Update the last activity time for a task"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['last_activity'] = time.time()

    def complete_task(self, task_id: str) -> None:
        """Mark a task as completed"""
        with self.lock:
            if task_id in self.tasks:
                # Calculate task duration
                duration = time.time() - self.tasks[task_id]['start_time']
                logger.info(f"Task {task_id} completed in {duration:.2f}s")
                del self.tasks[task_id]

    def is_task_timeout_imminent(self, task_id: str) -> bool:
        """Check if a task is about to timeout"""
        with self.lock:
            if task_id in self.tasks:
                task_info = self.tasks[task_id]
                elapsed = time.time() - task_info['start_time']
                remaining = task_info['timeout'] - elapsed

                # Return True if less than 20% of timeout remains
                return remaining < (task_info['timeout'] * 0.2)

            # Task not found
            return False

    def extend_task_timeout(self, task_id: str, additional_seconds: int = 10) -> None:
        """Extend the timeout for a task"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['timeout'] += additional_seconds
                logger.info(f"Extended timeout for task {task_id} by {additional_seconds}s")

    def get_task_elapsed_time(self, task_id: str) -> float:
        """Get the elapsed time for a task"""
        with self.lock:
            if task_id in self.tasks:
                return time.time() - self.tasks[task_id]['start_time']
            return 0.0

    def _monitor_tasks(self) -> None:
        """Background thread to monitor tasks and system resources"""
        check_interval = 1.0  # Check every second

        while not self._stop_monitoring.is_set():
            try:
                self._check_tasks()
                self._check_system_resources()

                # Sleep for a bit
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error in task monitor thread: {str(e)}")

    def _check_tasks(self) -> None:
        """Check for tasks that might be timing out"""
        current_time = time.time()
        tasks_to_warn = []

        with self.lock:
            for task_id, task_info in list(self.tasks.items()):
                elapsed = current_time - task_info['start_time']
                timeout = task_info['timeout']

                # Check if task is close to timing out (>80% of timeout elapsed)
                if elapsed > (timeout * 0.8) and task_info['warnings_issued'] < 2:
                    # Increase timeout for long-running tasks
                    self.tasks[task_id]['timeout'] += 5  # Add 5 seconds
                    self.tasks[task_id]['warnings_issued'] += 1

                    logger.warning(
                        f"Task {task_id} running for {elapsed:.1f}s (timeout: {timeout}s). "
                        f"Timeout extended."
                    )

    def _check_system_resources(self) -> None:
        """Check system resource usage and log warnings if needed"""
        try:
            # Get current process
            process = psutil.Process(os.getpid())

            # Memory usage
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # CPU usage
            cpu_percent = process.cpu_percent(interval=0.1)

            # Log if memory usage is high
            if memory_percent > self.warn_at_memory_percent:
                logger.warning(
                    f"High memory usage: {memory_percent:.1f}% "
                    f"({memory_info.rss / (1024 * 1024):.1f} MB)"
                )

                # Try to free some memory
                import gc
                gc.collect()

            # Log if CPU usage is very high
            if cpu_percent > 90:
                logger.warning(f"High CPU usage: {cpu_percent:.1f}%")

                # If we have active tasks, try to extend their timeouts
                with self.lock:
                    for task_id in self.tasks:
                        self.extend_task_timeout(task_id, 5)

        except Exception as e:
            # Don't let monitoring errors crash the thread
            logger.error(f"Error monitoring system resources: {str(e)}")


# Global instance
worker_guard = WorkerGuard()

# Start monitoring on import
worker_guard.start_monitoring()


def check_gunicorn_timeout():
    """
    Check and detect the Gunicorn worker timeout value from environment
    or configuration.
    """
    # Default worker timeout (30 seconds for most Gunicorn setups)
    default_timeout = 30

    # Try to get the timeout from environment
    try:
        timeout_str = os.environ.get('GUNICORN_TIMEOUT')
        if timeout_str and timeout_str.isdigit():
            return int(timeout_str)
    except:
        pass

    return default_timeout


# Register a signal handler for graceful timeouts
def timeout_handler(signum, frame):
    """Signal handler for timeouts"""
    logger.critical("Worker timeout signal received!")

    # Log information about active tasks
    with worker_guard.lock:
        for task_id, task_info in worker_guard.tasks.items():
            elapsed = time.time() - task_info['start_time']
            logger.critical(f"Task {task_id} running for {elapsed:.1f}s at timeout")

    # Default behavior - re-raise the signal
    signal.raise_signal(signum)


# Try to install the signal handler
try:
    # Register a signal handler for SIGTERM
    signal.signal(signal.SIGTERM, timeout_handler)
except Exception as e:
    logger.error(f"Failed to register timeout signal handler: {str(e)}")