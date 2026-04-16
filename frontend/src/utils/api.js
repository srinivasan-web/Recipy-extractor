const API_BASE =
  import.meta.env.VITE_API_BASE || "https://recipy-extractor.onrender.com/api";

const blockedScrapeIndicators = [
  "payment required",
  "forbidden",
  "rate-limited",
  "unavailable for legal reasons",
  "site blocks scraping",
  "sending `raw_text` directly",
];

export function createInitialRecipeState() {
  return {
    title: "",
    summary: "",
    cuisine: "",
    prep_time: "",
    cook_time: "",
    total_time: "",
    servings: "",
    difficulty: "",
    image_url: "",
    source_domain: "",
    ingredients: [],
    instructions: [],
    nutrition: null,
    substitutions: [],
    shopping_list: [],
    related_recipes: [],
  };
}

export function createInitialDashboardState() {
  return {
    total_recipes: 0,
    cuisines_tracked: 0,
    recipes_with_images: 0,
    average_ingredients: 0,
    latest_recipe: null,
    top_cuisines: [],
  };
}

function normalizeRecipeRecord(recipe) {
  if (!recipe || typeof recipe !== "object") {
    return createInitialRecipeState();
  }

  return {
    ...createInitialRecipeState(),
    ...recipe,
    summary: recipe.summary || recipe.description || recipe.excerpt || "",
    image_url:
      recipe.image_url ||
      recipe.imageUrl ||
      (Array.isArray(recipe.image) ? recipe.image[0]?.url || recipe.image[0] : null) ||
      recipe.image?.url ||
      recipe.image ||
      recipe.thumbnail_url ||
      recipe.thumbnailUrl ||
      "",
    source_domain: recipe.source_domain || recipe.sourceDomain || recipe.domain || "",
    ingredients: Array.isArray(recipe.ingredients) ? recipe.ingredients : [],
    instructions: Array.isArray(recipe.instructions) ? recipe.instructions : [],
    substitutions: Array.isArray(recipe.substitutions) ? recipe.substitutions : [],
    shopping_list: Array.isArray(recipe.shopping_list) ? recipe.shopping_list : [],
    related_recipes: Array.isArray(recipe.related_recipes) ? recipe.related_recipes : [],
    nutrition: recipe.nutrition && typeof recipe.nutrition === "object" ? recipe.nutrition : null,
  };
}

function normalizeDashboardResponse(dashboard) {
  if (!dashboard || typeof dashboard !== "object") {
    return createInitialDashboardState();
  }

  return {
    ...createInitialDashboardState(),
    ...dashboard,
    latest_recipe: dashboard.latest_recipe ? normalizeRecipeRecord(dashboard.latest_recipe) : null,
    top_cuisines: Array.isArray(dashboard.top_cuisines) ? dashboard.top_cuisines : [],
  };
}

function isBlockedScrapeMessage(message) {
  const normalized = message.toLowerCase();
  return blockedScrapeIndicators.some((indicator) => normalized.includes(indicator));
}

async function parseJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function createApiError(message, context = "api", type = "error") {
  return { type, context, message };
}

async function parseApiError(response, fallbackMessage) {
  const data = await parseJson(response);
  const message = data?.detail || fallbackMessage;

  if (isBlockedScrapeMessage(message)) {
    return createApiError(
      "That site blocked automatic scraping for this recipe URL. Try a different free, direct recipe page URL.",
      "extract",
      "warning",
    );
  }

  return createApiError(message);
}

async function fetchJson(path, { signal } = {}) {
  const response = await fetch(`${API_BASE}${path}`, { signal });
  if (!response.ok) {
    throw await parseApiError(response, "Request failed.");
  }
  return response.json();
}

export function isAbortError(error) {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function fetchDashboard({ signal } = {}) {
  const dashboard = await fetchJson("/dashboard", { signal });
  return normalizeDashboardResponse(dashboard);
}

export async function fetchRecipeHistory({ search = "", cuisine = "All", limit = 24, signal } = {}) {
  const params = new URLSearchParams();
  if (search.trim()) {
    params.set("search", search.trim());
  }
  if (cuisine && cuisine !== "All") {
    params.set("cuisine", cuisine);
  }
  params.set("limit", String(limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const recipes = await fetchJson(`/recipes${suffix}`, { signal });
  return Array.isArray(recipes) ? recipes.map(normalizeRecipeRecord) : [];
}

export async function extractRecipe({ url, signal }) {
  const trimmedUrl = url.trim();

  if (!trimmedUrl) {
    throw createApiError("Paste a direct recipe URL before extracting.", "extract");
  }

  const response = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url: trimmedUrl,
    }),
  });

  if (!response.ok) {
    throw await parseApiError(response, "Extraction failed.");
  }

  const recipe = await response.json();
  return normalizeRecipeRecord(recipe);
}

export async function fetchRecipeById(id, { signal } = {}) {
  const recipe = await fetchJson(`/recipes/${id}`, { signal });
  return normalizeRecipeRecord(recipe);
}
