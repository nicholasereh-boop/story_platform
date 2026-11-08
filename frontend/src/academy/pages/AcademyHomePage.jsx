import { Link } from "react-router-dom";
import { SITE_NAME } from "../../config";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";

const STEPS = [
  { icon: "▶", title: "Watch", text: "Each lesson is a short video. Your progress is saved on the server, so you can carry on from any device." },
  { icon: "💬", title: "Comment", text: "In the free courses, share what you learned in a short comment under the lesson." },
  { icon: "🔓", title: "Unlock", text: "Your comment opens the next lesson. The course introduction is always open, no comment needed." },
];

export default function AcademyHomePage() {
  useDocumentMeta({ title: "Academy", description: `Learn to build websites with free and premium video courses from ${SITE_NAME}.` });
  return (
    <div className="ac-container">
      <section className="ac-hero" aria-labelledby="ac-hero-h">
        <p className="ac-eyebrow">Learn · Build · Ship</p>
        <h1 id="ac-hero-h">Learn to build websites, one lesson at a time</h1>
        <p className="ac-lede">Free tutorials to get you started, and premium courses when you want to go deeper. Watch, practise, and keep your progress wherever you log in.</p>
        <div className="ac-actions">
          <Link to="/academy/free" className="ac-btn ac-btn-primary">Start free</Link>
          <Link to="/academy/paid" className="ac-btn ac-btn-ghost">See premium courses</Link>
        </div>
      </section>

      <section className="ac-split" aria-label="Choose your path">
        <Link to="/academy/free" className="ac-card ac-card-free">
          <span className="ac-chip ac-chip-free">Free</span>
          <h2>Free tutorials</h2>
          <p>Beginner-friendly courses. Finish a lesson, leave a comment, and the next one opens.</p>
          <span className="ac-more">Browse free courses →</span>
        </Link>
        <Link to="/academy/paid" className="ac-card ac-card-paid">
          <span className="ac-chip ac-chip-paid">Premium</span>
          <h2>Paid tutorials</h2>
          <p>In-depth courses with every lesson open as soon as you buy. Pay once, learn at your pace.</p>
          <span className="ac-more">Browse premium courses →</span>
        </Link>
      </section>

      <section aria-labelledby="ac-how-h">
        <h2 id="ac-how-h" className="ac-h2">How the free courses work</h2>
        <ol className="ac-steps">
          {STEPS.map((s, i) => (
            <li key={s.title} className="ac-step">
              <span className="ac-step-icon" aria-hidden="true">{s.icon}</span>
              <h3><span className="ac-step-n">{i + 1}.</span> {s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}