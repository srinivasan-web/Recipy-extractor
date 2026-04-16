const suggestedUrls = [
  "https://www.bbcgoodfood.com/recipes/easy-pancakes",
  "https://www.simplyrecipes.com/recipes/perfect_guacamole/",
  "https://www.simplyrecipes.com/recipes/spaghetti_and_meatballs/",
];

function ExtractForm({ extracting, onSubmit, onUrlChange, url }) {
  return (
    <form className="extract-card" onSubmit={onSubmit}>
      <div className="section-kicker">Live extractor</div>
      <h2 className="card-title">Turn a messy recipe page into a structured cooking asset</h2>
      <p className="card-copy">
        The backend scrapes the page, enriches it with Gemini, and stores an image-rich record for
        browsing later.
      </p>

      <label className="field-label" htmlFor="recipe-url">
        Direct recipe URL
      </label>
      <div className="url-input-row">
        <input
          id="recipe-url"
          className="input url-input"
          disabled={extracting}
          onChange={(event) => onUrlChange(event.target.value)}
          placeholder="https://example.com/recipe/single-dish-name"
          type="url"
          value={url}
        />
        <button className="primary-button primary-button-compact" disabled={extracting} type="submit">
          {extracting ? (
            <span className="button-content">
              <span aria-hidden="true" className="spinner spinner-inline" />
              Extracting
            </span>
          ) : (
            "Extract"
          )}
        </button>
      </div>

      <div className="mini-note">
        Best results come from direct recipe pages with ingredients and instructions visible on the
        page.
      </div>

      <div className="suggestions-block">
        <div className="field-label">Try a tested sample URL</div>
        <div className="suggestion-list">
          {suggestedUrls.map((suggestedUrl) => (
            <button
              key={suggestedUrl}
              className="suggestion-chip"
              disabled={extracting}
              onClick={() => onUrlChange(suggestedUrl)}
              type="button"
            >
              {new URL(suggestedUrl).hostname.replace("www.", "")}
            </button>
          ))}
        </div>
      </div>

      <div className="extract-checklist">
        <div>Image capture from the source page</div>
        <div>Cached repeat extracts for faster reuse</div>
        <div>Search-friendly recipe library with summaries</div>
      </div>
    </form>
  );
}

export default ExtractForm;
