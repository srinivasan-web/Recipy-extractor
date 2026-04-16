import { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";
import AlertBanner from "./components/AlertBanner";
import DashboardSpotlight from "./components/DashboardSpotlight";
import ExtractForm from "./components/ExtractForm";
import HistoryPanel from "./components/HistoryPanel";
import RecipeModal from "./components/RecipeModal";
import ResultPanel from "./components/ResultPanel";
import StatsStrip from "./components/StatsStrip";
import {
  createInitialDashboardState,
  createInitialRecipeState,
  extractRecipe,
  fetchDashboard,
  fetchRecipeById,
  fetchRecipeHistory,
  isAbortError,
} from "./utils/api";

function App() {
  const emptyRecipe = createInitialRecipeState();
  const emptyDashboard = createInitialDashboardState();
  const [activeTab, setActiveTab] = useState("extract");
  const [url, setUrl] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loadingRecipeId, setLoadingRecipeId] = useState(null);
  const [alert, setAlert] = useState(null);
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [history, setHistory] = useState([]);
  const [currentRecipe, setCurrentRecipe] = useState(emptyRecipe);
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [historySearch, setHistorySearch] = useState("");
  const [selectedCuisine, setSelectedCuisine] = useState("All");
  const [refreshToken, setRefreshToken] = useState(0);
  const [recipeCache, setRecipeCache] = useState({});
  const deferredHistorySearch = useDeferredValue(historySearch);
  const extractControllerRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    void loadDashboard(controller.signal);
    return () => controller.abort();
  }, [refreshToken]);

  useEffect(() => {
    const controller = new AbortController();
    void loadHistory(controller.signal);
    return () => controller.abort();
  }, [deferredHistorySearch, selectedCuisine, refreshToken]);

  async function loadDashboard(signal) {
    setDashboardLoading(true);
    try {
      const data = await fetchDashboard({ signal });
      startTransition(() => {
        setDashboard(data);
      });
      setAlert((currentAlert) => (currentAlert?.context === "dashboard" ? null : currentAlert));
    } catch (fetchError) {
      if (isAbortError(fetchError)) {
        return;
      }
      setAlert({
        type: "error",
        context: "dashboard",
        message: fetchError.message || "Unable to load dashboard overview.",
      });
    } finally {
      setDashboardLoading(false);
    }
  }

  async function loadHistory(signal) {
    setHistoryLoading(true);
    try {
      const data = await fetchRecipeHistory({
        search: deferredHistorySearch,
        cuisine: selectedCuisine,
        signal,
      });
      startTransition(() => {
        setHistory(data);
      });
      setAlert((currentAlert) => (currentAlert?.context === "history" ? null : currentAlert));
    } catch (fetchError) {
      if (isAbortError(fetchError)) {
        return;
      }
      setAlert({
        type: "error",
        context: "history",
        message: fetchError.message || "Unable to load extraction history.",
      });
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handleExtract(event) {
    event.preventDefault();
    setExtracting(true);
    setAlert(null);
    extractControllerRef.current?.abort();
    const controller = new AbortController();
    extractControllerRef.current = controller;

    try {
      const data = await extractRecipe({ url, signal: controller.signal });
      setCurrentRecipe(data);
      setSelectedRecipe(data);
      setUrl("");
      setRecipeCache((currentCache) => ({ ...currentCache, [data.id]: data }));
      setActiveTab("extract");
      setRefreshToken((current) => current + 1);
    } catch (fetchError) {
      if (isAbortError(fetchError)) {
        return;
      }
      setAlert(fetchError);
    } finally {
      setExtracting(false);
      if (extractControllerRef.current === controller) {
        extractControllerRef.current = null;
      }
    }
  }

  async function openRecipe(id) {
    if (recipeCache[id]) {
      setSelectedRecipe(recipeCache[id]);
      return;
    }

    setDetailLoading(true);
    setLoadingRecipeId(id);
    setAlert(null);
    const controller = new AbortController();
    try {
      const data = await fetchRecipeById(id, { signal: controller.signal });
      setRecipeCache((currentCache) => ({ ...currentCache, [id]: data }));
      setSelectedRecipe(data);
    } catch (fetchError) {
      if (isAbortError(fetchError)) {
        return;
      }
      setAlert({
        type: "error",
        context: "detail",
        message: fetchError.message || "Unable to load recipe details.",
      });
    } finally {
      setDetailLoading(false);
      setLoadingRecipeId(null);
    }
  }

  const cuisineOptions = ["All"];
  for (const recipe of history) {
    if (recipe.cuisine && !cuisineOptions.includes(recipe.cuisine)) {
      cuisineOptions.push(recipe.cuisine);
    }
  }
  for (const entry of dashboard.top_cuisines || []) {
    if (entry.cuisine && !cuisineOptions.includes(entry.cuisine)) {
      cuisineOptions.push(entry.cuisine);
    }
  }

  return (
    <div className="shell">
      <div className="backdrop" />
      <main className="app">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Modern Recipe Intelligence Workspace</p>
            <h1>Recipe Extractor & Meal Planner</h1>
            <p className="lead">
              Structured extraction, source images, searchable history, and a faster dashboard for
              turning recipe URLs into reusable cooking assets.
            </p>
            <div className="hero-tags">
              <span>Animated UI</span>
              <span>Abortable requests</span>
              <span>Search-ready library</span>
              <span>Image-rich metadata</span>
            </div>
          </div>
          <StatsStrip dashboard={dashboard} dashboardLoading={dashboardLoading} />
        </section>

        <section className="panel">
          <div className="tabs">
            <button
              className={activeTab === "extract" ? "tab active" : "tab"}
              onClick={() => setActiveTab("extract")}
              type="button"
            >
              Extract Recipe
            </button>
            <button
              className={activeTab === "history" ? "tab active" : "tab"}
              onClick={() => setActiveTab("history")}
              type="button"
            >
              History
            </button>
          </div>

          <AlertBanner alert={alert} />

          <DashboardSpotlight dashboard={dashboard} onOpenRecipe={openRecipe} />

          {activeTab === "extract" ? (
            <div className="grid">
              <ExtractForm
                extracting={extracting}
                onSubmit={handleExtract}
                onUrlChange={setUrl}
                url={url}
              />

              <ResultPanel
                currentRecipe={currentRecipe}
                extracting={extracting}
                onInspect={() => setSelectedRecipe(currentRecipe.id ? currentRecipe : null)}
              />
            </div>
          ) : (
            <HistoryPanel
              cuisine={selectedCuisine}
              cuisines={cuisineOptions}
              detailLoading={detailLoading}
              history={history}
              historyLoading={historyLoading}
              onCuisineChange={setSelectedCuisine}
              loadingRecipeId={loadingRecipeId}
              onOpenRecipe={openRecipe}
              onRefresh={() => setRefreshToken((current) => current + 1)}
              onSearchChange={setHistorySearch}
              search={historySearch}
            />
          )}
        </section>

        <RecipeModal
          detailLoading={detailLoading}
          onClose={() => setSelectedRecipe(null)}
          recipe={selectedRecipe}
        />
      </main>
    </div>
  );
}

export default App;
