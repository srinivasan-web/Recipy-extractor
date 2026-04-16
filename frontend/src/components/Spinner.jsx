function Spinner({ label = "Loading" }) {
  return (
    <div aria-live="polite" className="spinner-wrap" role="status">
      <span aria-hidden="true" className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export default Spinner;
