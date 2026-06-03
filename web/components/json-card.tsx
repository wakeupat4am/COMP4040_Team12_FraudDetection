import { prettyJson } from "@/lib/formatters";

export function JsonCard({ title, value }: { title: string; value: unknown }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>{title}</h3>
      </div>
      <pre className="json-block">{prettyJson(value)}</pre>
    </section>
  );
}
