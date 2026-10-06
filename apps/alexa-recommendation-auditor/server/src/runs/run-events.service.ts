import { Injectable, MessageEvent } from "@nestjs/common";
import { Observable, ReplaySubject } from "rxjs";

@Injectable()
export class RunEventsService {
  private readonly streams = new Map<string, ReplaySubject<MessageEvent>>();

  stream(runId: string): Observable<MessageEvent> {
    return this.subject(runId).asObservable();
  }

  emit(runId: string, type: string, data: unknown) {
    const eventData: string | object = typeof data === "string"
      ? data
      : data !== null && typeof data === "object"
        ? data as object
        : { value: data };
    this.subject(runId).next({ type, data: eventData, id: `${Date.now()}` });
  }

  private subject(runId: string) {
    let subject = this.streams.get(runId);
    if (!subject) {
      subject = new ReplaySubject<MessageEvent>(1);
      this.streams.set(runId, subject);
    }
    return subject;
  }
}
