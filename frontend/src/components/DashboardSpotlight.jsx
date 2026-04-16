function DashboardSpotlight({ dashboard, onOpenRecipe }) {
  return (
    <section className="spotlight-grid">
      <article className="spotlight-card">
        <div className="section-kicker">Latest extraction</div>
        {dashboard.latest_recipe ? (
          <>
            <h2 className="spotlight-title">{dashboard.latest_recipe.title || "Untitled recipe"}</h2>
            <p className="spotlight-copy">
              {dashboard.latest_recipe.summary || "Freshly structured and ready to inspect in detail."}
            </p>
            <div className="meta-strip meta-strip-tight">
              <span>{dashboard.latest_recipe.cuisine || "Cuisine pending"}</span>
              <span>{dashboard.latest_recipe.total_time || "Timing pending"}</span>
              <span>{dashboard.latest_recipe.source_domain || "Source pending"}</span>
            </div>
            <button
              className="ghost-button"
              onClick={() => void onOpenRecipe(dashboard.latest_recipe.id)}
              type="button"
            >
              Open latest recipe
            </button>
          </>
        ) : (
          <>
            <h2 className="spotlight-title">No recipe extracted yet</h2>
            <p className="spotlight-copy">
              Kick off the first extraction and this panel will surface the freshest record here.
            </p>
          </>
        )}
      </article>

      <article className="spotlight-card">
        <div className="section-kicker">Top cuisines</div>
        <h2 className="spotlight-title">What the library is learning</h2>
        <div className="cuisine-cloud">
          {dashboard.top_cuisines?.length ? (
            dashboard.top_cuisines.map((entry) => (
              <span key={entry.cuisine} className="cuisine-pill">
                {entry.cuisine}
                <strong>{entry.count}</strong>
              </span>
            ))
          ) : (
            <p className="spotlight-copy">Cuisine insights will appear after a few extractions.</p>
          )}
        </div>
      </article>
    </section>
  );
}

export default DashboardSpotlight;
