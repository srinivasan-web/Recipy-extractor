function StatsStrip({ dashboard, dashboardLoading }) {
  const stats = [
    {
      label: "Recipes captured",
      value: dashboard.total_recipes,
      caption: "Structured and saved in your library",
    },
    {
      label: "Cuisine signals",
      value: dashboard.cuisines_tracked,
      caption: "Distinct cuisines discovered so far",
    },
    {
      label: "Recipes with images",
      value: dashboard.recipes_with_images,
      caption: "Pages that returned visual metadata",
    },
    {
      label: "Avg ingredients",
      value: dashboard.average_ingredients || 0,
      caption: "Mean ingredient count per recipe",
    },
  ];

  return (
    <div className="stats-strip">
      {stats.map((stat, index) => (
        <article
          key={stat.label}
          className={dashboardLoading ? "stat-card stat-card-loading" : "stat-card"}
          style={{ animationDelay: `${index * 120}ms` }}
        >
          <p className="stat-label">{stat.label}</p>
          <strong className="stat-value">{dashboardLoading ? "..." : stat.value}</strong>
          <span className="stat-caption">{stat.caption}</span>
        </article>
      ))}
    </div>
  );
}

export default StatsStrip;
