"""Train and evaluate a heterogeneous GNN on the saved PaySim splits."""

from pathlib import Path

from train_paysim_four_models import (
    PaySimHeteroGNN,
    build_graph_df_from_splits,
    build_hetero_data,
    evaluate_graph_model,
    load_saved_splits,
    print_result,
    train_graph_model,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "models" / "paysim_hetero_gnn"


def main() -> None:
    train_df, val_df, test_df = load_saved_splits()
    graph_df = build_graph_df_from_splits(train_df, val_df, test_df)
    data = build_hetero_data(graph_df)
    in_dims = {node_type: data[node_type].x.size(-1) for node_type in data.node_types}
    model = PaySimHeteroGNN(data.metadata(), in_dims, hidden_dim=64)
    model, training_summary = train_graph_model(data, model, epochs=25)
    result = evaluate_graph_model("Heterogeneous GNN", model, data, graph_df, training_summary, OUTPUT_DIR)
    print_result(result)


if __name__ == "__main__":
    main()
