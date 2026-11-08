import { NavLink } from "react-router-dom";

export default function NewsroomTabs() {
  const link = ({ isActive }) => (isActive ? "nw-tab is-active" : "nw-tab");
  return (
    <nav aria-label="Newsroom" className="nw-tabs nw-admin-tabs">
      <NavLink to="/admin/news" end className={link}>Articles</NavLink>
      <NavLink to="/admin/news/import" className={link}>Import</NavLink>
      <NavLink to="/admin/news/sources" className={link}>Sources and rights</NavLink>
      <NavLink to="/admin/news/takedowns" className={link}>Complaints</NavLink>
      <NavLink to="/admin/news/comments" className={link}>Comments</NavLink>
    </nav>
  );
}
