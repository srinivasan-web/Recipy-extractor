import Spinner from "./Spinner";

function HistoryPanel({
  cuisine,
  cuisines,
  detailLoading,
  history,
  historyLoading,
  onCuisineChange,
  loadingRecipeId,
  onOpenRecipe,
  onRefresh,
  onSearchChange,
  search,
}) {
  return (
    <section className="history-card">
      <div className="history-header">
        <div>
          <p className="eyebrow">Stored Recipes</p>
          <h2>Recipe Library</h2>
        </div>
        <div className="history-actions">
          <input
            className="input history-search"
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search title, cuisine, or domain"
            type="search"
            value={search}
          />
          <select
            className="input history-select"
            onChange={(event) => onCuisineChange(event.target.value)}
            value={cuisine}
          >
            {cuisines.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <button
            className="ghost-button"
            disabled={historyLoading}
            onClick={onRefresh}
            type="button"
          >
            {historyLoading ? (
              <span className="button-content">
                <span aria-hidden="true" className="spinner spinner-inline" />
                Refreshing...
              </span>
            ) : (
              "Refresh"
            )}
          </button>
        </div>
      </div>

      {historyLoading ? <Spinner label="Loading recipe history..." /> : null}

      <div className="history-grid">
        {history.length ? (
          history.map((recipe) => (
            <article key={recipe.id} className="history-recipe-card">
              <div className="history-image-shell">
                {recipe.image_url ? (
                  <img
                    alt={recipe.title || "Recipe preview"}
                    className="history-image"
                    src={recipe.image_url}
                  />
                ) : (
                  <div className="history-image history-image-fallback">No preview</div>
                )}
              </div>

              <div className="history-card-copy">
                <div className="meta-strip meta-strip-tight">
                  <span>{recipe.cuisine || "Unknown cuisine"}</span>
                  <span>{recipe.source_domain || "Unknown source"}</span>
                </div>
                <h3>{recipe.title || "Untitled recipe"}</h3>
                <p>{recipe.summary || "Structured recipe ready for detail view."}</p>
                <div className="history-footer">
                  <span>{new Date(recipe.created_at).toLocaleDateString()}</span>
                  <span>{recipe.total_time || "Timing pending"}</span>
                  <button
                    className="inline-button"
                    disabled={detailLoading}
                    onClick={() => void onOpenRecipe(recipe.id)}
                    type="button"
                  >
                    {detailLoading && loadingRecipeId === recipe.id ? "Loading..." : "Inspect"}
                  </button>
                </div>
              </div>
            </article>
          ))
        ) : (
          <div className="history-empty">
            <h3>No recipes match this view yet</h3>
            <p>Extract a recipe or loosen the filters to repopulate the library.</p>
          </div>
        )}
      </div>
    </section>
  );
}

export default HistoryPanel;
