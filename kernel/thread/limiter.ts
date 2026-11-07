/** Async capacity limits for process-local work. */

class ValueError extends Error {
  constructor(message = '') {
    super(message)
    this.name = 'ValueError'
  }
}

export class AsyncTaskLimiter {
  capacity: number
  private availablePermits: number
  private waiters: Array<() => void> = []

  constructor(capacity: number) {
    if (capacity < 1) throw new ValueError('capacity must be at least 1')
    this.capacity = capacity
    this.availablePermits = capacity
  }

  async slot<T>(body: () => Promise<T> | T): Promise<T> {
    await this.acquire()
    try {
      return await body()
    } finally {
      this.release()
    }
  }

  expand_to(capacity: number): void {
    const next = Number(capacity)
    if (next < 1) throw new ValueError('capacity must be at least 1')
    const extra = next - this.capacity
    if (extra <= 0) return
    for (let index = 0; index < extra; index += 1) this.release()
    this.capacity = next
  }

  get available(): number {
    return Math.max(0, this.availablePermits)
  }

  private acquire(): Promise<void> {
    if (this.availablePermits > 0) {
      this.availablePermits -= 1
      return Promise.resolve()
    }
    return new Promise(resolve => {
      this.waiters.push(() => {
        this.availablePermits -= 1
        resolve()
      })
    })
  }

  private release(): void {
    const waiter = this.waiters.shift()
    if (waiter) {
      this.availablePermits += 1
      waiter()
      return
    }
    this.availablePermits += 1
  }
}
