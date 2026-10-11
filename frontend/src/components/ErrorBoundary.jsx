import { Component } from "react";

// Catches a crash inside its children so a bug in the editor shows a message instead of a white screen.
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Editor crashed:", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="notice error" role="alert">
        <strong>{this.props.title || "Something went wrong here."}</strong>
        <p>Your last saved version is safe on the server. Try again, or reload the page.</p>
        <button type="button" className="btn secondary small" onClick={() => this.setState({ error: null })}>
          Try again
        </button>
      </div>
    );
  }
}
