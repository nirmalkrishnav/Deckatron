/** Explicit non-generation result; request text is preserved without interpreting it. */
export class DeckBuildResult {
  readonly status = "placeholder";
  readonly message = "Deck generation is not implemented. No presentation was created.";

  constructor(readonly request: string) {}

  /** Return only the application fields carried in an A2A structured data part. */
  toJSON(): { status: "placeholder"; request: string; message: string } {
    return {
      status: this.status,
      request: this.request,
      message: this.message,
    };
  }
}
