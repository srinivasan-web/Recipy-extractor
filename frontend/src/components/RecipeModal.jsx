import Spinner from "./Spinner";

function RecipeModal({ detailLoading, onClose, recipe }) {
  if (!recipe) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <section
        aria-modal="true"
        className="modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Recipe Details</p>
            <h2>{recipe.title || "Untitled recipe"}</h2>
            <p className="modal-summary">
              {recipe.summary || "Structured recipe details for planning, cooking, and reuse."}
            </p>
          </div>
          <button className="ghost-button" disabled={detailLoading} onClick={onClose} type="button">
            Close
          </button>
        </div>

        <div className="detail-stack">
          {detailLoading ? <Spinner label="Loading recipe details..." /> : null}
          <div className="modal-hero">
            <div className="recipe-image-shell modal-image-shell">
              {recipe.image_url ? (
                <img alt={recipe.title || "Recipe preview"} className="recipe-image" src={recipe.image_url} />
              ) : (
                <div className="recipe-image recipe-image-placeholder">No image metadata returned</div>
              )}
            </div>
            <div className="modal-meta-column">
              <div className="meta-strip">
                <span>{recipe.cuisine || "Cuisine pending"}</span>
                <span>{recipe.total_time || "Time pending"}</span>
                <span>{recipe.servings || "Servings pending"}</span>
                <span>{recipe.source_domain || "Source pending"}</span>
              </div>
              <p>
                <strong>Source URL:</strong> {recipe.url}
              </p>
              <p>
                <strong>Difficulty:</strong> {recipe.difficulty || "Unknown"}
              </p>
            </div>
          </div>

          <div className="modal-grid">
            <article className="subcard">
              <h3>Ingredients</h3>
              <ul>
                {recipe.ingredients?.length ? (
                  recipe.ingredients.map((ingredient, index) => (
                    <li key={`${ingredient.item}-${index}`}>
                      {[ingredient.quantity, ingredient.unit, ingredient.item].filter(Boolean).join(" ")}
                    </li>
                  ))
                ) : (
                  <li>No ingredients provided.</li>
                )}
              </ul>
            </article>

            <article className="subcard">
              <h3>Instructions</h3>
              <ol>
                {recipe.instructions?.length ? (
                  recipe.instructions.map((step, index) => <li key={`${step}-${index}`}>{step}</li>)
                ) : (
                  <li>No instructions provided.</li>
                )}
              </ol>
            </article>

            <article className="subcard">
              <h3>Substitutions</h3>
              <ul>
                {recipe.substitutions?.length ? (
                  recipe.substitutions.map((item, index) => (
                    <li key={`${item.ingredient}-${index}`}>
                      {(item.ingredient || "Ingredient") +
                        ": " +
                        (item.alternatives?.join(", ") || "No alternatives")}
                    </li>
                  ))
                ) : (
                  <li>No substitutions provided.</li>
                )}
              </ul>
            </article>

            <article className="subcard">
              <h3>Related recipes</h3>
              <ul>
                {recipe.related_recipes?.length ? (
                  recipe.related_recipes.map((recipeName) => <li key={recipeName}>{recipeName}</li>)
                ) : (
                  <li>No related recipes listed.</li>
                )}
              </ul>
            </article>
          </div>
        </div>
      </section>
    </div>
  );
}

export default RecipeModal;
