export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <section className="panel empty-state">
      <h3>{title}</h3>
      <p>{description}</p>
    </section>
  );
}
