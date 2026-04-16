CREATE TABLE IF NOT EXISTS recipes (
  id SERIAL PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  summary TEXT,
  cuisine TEXT,
  prep_time TEXT,
  cook_time TEXT,
  total_time TEXT,
  servings TEXT,
  difficulty TEXT,
  image_url TEXT,
  source_domain TEXT,
  ingredients JSONB NOT NULL DEFAULT '[]'::jsonb,
  instructions JSONB NOT NULL DEFAULT '[]'::jsonb,
  nutrition JSONB,
  substitutions JSONB NOT NULL DEFAULT '[]'::jsonb,
  shopping_list JSONB NOT NULL DEFAULT '[]'::jsonb,
  related_recipes JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS recipes_created_at_idx ON recipes (created_at DESC);
CREATE INDEX IF NOT EXISTS recipes_source_domain_idx ON recipes (source_domain);
