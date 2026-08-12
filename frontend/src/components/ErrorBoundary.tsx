import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("ErrorBoundary caught:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          padding: "2rem",
          textAlign: "center",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.25rem" }}>Something went wrong</h1>
        <pre
          style={{
            maxWidth: "42rem",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            background: "#111",
            color: "#f66",
            padding: "0.75rem 1rem",
            borderRadius: "0.5rem",
            fontSize: "0.8rem",
            textAlign: "left",
          }}
        >
          {this.state.error.message}
        </pre>
        <button
          onClick={() => window.location.reload()}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: "0.375rem",
            border: "none",
            background: "#3182ce",
            color: "#fff",
            cursor: "pointer",
          }}
        >
          Reload page
        </button>
      </div>
    );
  }
}
