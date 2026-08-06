"""
AI Request Manager for Fashion Trend Monitor.

Centralizes and manages all outbound AI API requests.
Implements queuing, rate limiting, retries with exponential backoff,
and isolates errors so the pipeline can continue.
"""

import time
import logging
from typing import List, Callable, Any

logger = logging.getLogger(__name__)


class AIRequestManager:
    """Manages AI requests with rate limits, delays, and backoff."""

    def __init__(self, max_retries: int = 4, delay_seconds: float = 1.5):
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        
        # Statistics
        self.submitted = 0
        self.completed = 0
        self.failed = 0
        self.retries = 0
        self.total_latency = 0.0

    def submit_batch(self, items: List[Any], func: Callable[[Any, int], Any]) -> List[Any]:
        """
        Process a batch of items synchronously with strict delays between them.
        
        Args:
            items: The items to process (e.g., Products)
            func: The function to call. It should take (item, max_retries) and return the modified item.
        """
        if not items:
            return []
            
        self.submitted += len(items)
        logger.info(f"[AIRequestManager] Processing batch of {len(items)} items...")
        
        results = []
        for index, item in enumerate(items):
            start_time = time.time()
            try:
                # Execute the provided function
                result = func(item, self.max_retries)
                self.completed += 1
                results.append(result)
            except Exception as e:
                logger.error(f"[AIRequestManager] Unhandled failure on item: {e}")
                self.failed += 1
                results.append(item)
                
            latency = time.time() - start_time
            self.total_latency += latency
            
            # Enforce delay between requests (except the last one)
            if index < len(items) - 1 and self.delay_seconds > 0:
                time.sleep(self.delay_seconds)
                
        self._log_summary()
        return results

    def _log_summary(self) -> None:
        """Log concise production summary."""
        avg_latency = self.total_latency / max(1, self.completed + self.failed)
        logger.info(
            f"[AIRequestManager Summary] "
            f"Submitted: {self.submitted} | Completed: {self.completed} | "
            f"Failed: {self.failed} | Avg Latency: {avg_latency:.2f}s"
        )
