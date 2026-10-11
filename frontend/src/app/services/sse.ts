import { Observable } from 'rxjs';

/**
 * POSTs JSON and reads a Server-Sent Events response as it arrives (EventSource can't POST).
 * Each "data:" message is parsed as JSON; a message with type "error" ends the stream with that message.
 */
export function postEventStream<T>(url: string, body: unknown): Observable<T> {
  return new Observable<T>((subscriber) => {
    const controller = new AbortController();
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok || !res.body) throw new Error(`The server replied with ${res.status}.`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let end: number;
          while ((end = buffer.indexOf('\n\n')) >= 0) {
            const line = buffer.slice(0, end).split('\n').find((l) => l.startsWith('data: '));
            buffer = buffer.slice(end + 2);
            if (!line) continue;
            const event = JSON.parse(line.slice(6));
            if (event.type === 'error') throw new Error(event.message);
            subscriber.next(event as T);
          }
        }
        subscriber.complete();
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') subscriber.error(err);
      });
    return () => controller.abort();
  });
}
