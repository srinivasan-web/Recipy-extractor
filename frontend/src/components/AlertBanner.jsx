function AlertBanner({ alert }) {
  if (!alert) {
    return null;
  }

  return (
    <div className={alert.type === "warning" ? "alert alert-warning" : "alert"} role="alert">
      <div className="alert-badge">{alert.type === "warning" ? "Heads up" : "Something went wrong"}</div>
      <p className="alert-message">{alert.message}</p>
    </div>
  );
}

export default AlertBanner;
