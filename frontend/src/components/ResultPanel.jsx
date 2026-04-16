import Spinner from "./Spinner";

function ResultPanel({ currentRecipe, extracting, onInspect }) {
  const hasRecipe = Boolean(currentRecipe.title || currentRecipe.ingredients?.length);

  return (
    <section className="result-card">
      {extracting ? (
        <div className="loading-overlay">
          <Spinner label="Calling the API and building your recipe..." />
        </div>
      ) : null}
      {hasRecipe ? (
        <>
          <div className="result-hero">
            <div className="result-copy">
              <div className="result-header">
                <div>
                  <p className="eyebrow">Structured Output</p>
                  <h2>{currentRecipe.title}</h2>
                </div>
                {currentRecipe.cached ? <span className="pill">Cached</span> : null}
              </div>

              <p className="result-summary">
                {currentRecipe.summary || "Your latest recipe is structured and ready for planning."}
              </p>

              <div className="meta-strip">
                <span>{currentRecipe.cuisine || "Cuisine pending"}</span>
                <span>{currentRecipe.total_time || "Time pending"}</span>
                <span>{currentRecipe.servings || "Servings pending"}</span>
                <span>{currentRecipe.source_domain || "Domain pending"}</span>
              </div>
            </div>

            <div className="recipe-image-shell">
              {currentRecipe.image_url ? (
                <img
                  alt={currentRecipe.title || "Recipe preview"}
                  className="recipe-image"
                  src={currentRecipe.image_url}
                />
              ) : (
                <div className="recipe-image recipe-image-placeholder">No image metadata returned</div>
              )}
            </div>
          </div>

          <div className="result-grid">
            <article className="subcard">
              <h3>Ingredients</h3>
              <ul>
                {currentRecipe.ingredients?.length ? (
                  currentRecipe.ingredients.map((ingredient, index) => (
                    <li key={`${ingredient.item}-${index}`}>
                      {[ingredient.quantity, ingredient.unit, ingredient.item].filter(Boolean).join(" ")}
                    </li>
                  ))
                ) : (
                  <li>No ingredients yet.</li>
                )}
              </ul>
            </article>

            <article className="subcard">
              <h3>Instructions</h3>
              <ol>
                {currentRecipe.instructions?.length ? (
                  currentRecipe.instructions.slice(0, 5).map((step, index) => (
                    <li key={`${step}-${index}`}>{step}</li>
                  ))
                ) : (
                  <li>No instructions yet.</li>
                )}
              </ol>
            </article>

            <article className="subcard">
              <h3>Nutrition</h3>
              {currentRecipe.nutrition ? (
                <dl className="nutrition-grid">
                  {Object.entries(currentRecipe.nutrition).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{value || "n/a"}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p>Nutrition data not available.</p>
              )}
            </article>

            <article className="subcard">
              <h3>Shopping List</h3>
              <ul>
                {currentRecipe.shopping_list?.length ? (
                  currentRecipe.shopping_list.map((item, index) => (
                    <li key={`${item.item}-${index}`}>
                      <strong>{item.item || "Unknown item"}</strong>
                      {" - "}
                      {(item.quantity || "quantity n/a") + " - " + (item.category || "category n/a")}
                    </li>
                  ))
                ) : (
                  <li>No shopping items yet.</li>
                )}
              </ul>
            </article>
          </div>

          <div className="result-actions">
            <button className="ghost-button" onClick={onInspect} type="button">
              Open full recipe view
            </button>
          </div>
        </>
      ) : (
        <div className="result-empty">
          <div className="section-kicker">Structured output</div>
          <h2 className="card-title">Waiting for your next URL</h2>
          <p className="card-copy">
            Extract a recipe to populate this workspace with image previews, nutrition, shopping
            guidance, and reusable history metadata.
          </p>
        </div>
      )}
    </section>
  );
}

export default ResultPanel;
