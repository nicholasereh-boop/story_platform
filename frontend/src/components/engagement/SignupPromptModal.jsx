import { Link } from "react-router-dom";
import GoogleButton from "../auth/GoogleButton";
import Modal from "../Modal";

// Friendly invitation for anonymous visitors. Built on Modal, so focus is trapped, Esc closes and focus returns
// to whatever opened it. Closing (Esc, backdrop, X or the Close button) all call onClose.
export default function SignupPromptModal({ onClose, from = "/" }) {
  const state = { from };
  return (
    <Modal title="Join the conversation" onClose={onClose}>
      <p>Create a free account to like stories, comment and keep the conversation going.</p>
      <div className="prompt-actions">
        <GoogleButton />
        <Link className="btn block" to="/register" state={state}>Sign up with email</Link>
        <Link className="btn secondary block" to="/login" state={state}>Log in</Link>
      </div>
      <div className="row end">
        <button type="button" className="btn ghost" data-autofocus onClick={onClose}>Close</button>
      </div>
    </Modal>
  );
}
