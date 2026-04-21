-- ============================================================
-- Fridge2Dish Agent — PostgreSQL DDL
-- ============================================================

-- 확장 (UUID 등 필요 시 사용)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. users
-- ============================================================
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(100) NOT NULL UNIQUE,
    email       VARCHAR(255) UNIQUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. user_preferences
-- ============================================================
CREATE TABLE user_preferences (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    spice_level         SMALLINT     NOT NULL DEFAULT 2          -- 0(없음) ~ 5(매우 매움)
                            CHECK (spice_level BETWEEN 0 AND 5),
    disliked_ingredients TEXT[]       NOT NULL DEFAULT '{}',     -- 비선호 재료 목록
    allergies           TEXT[]       NOT NULL DEFAULT '{}',      -- 알레르기 재료 목록
    dietary_tags        TEXT[]       NOT NULL DEFAULT '{}',      -- 채식, 글루텐프리 등
    cooking_skill       VARCHAR(20)  NOT NULL DEFAULT 'beginner' -- beginner / intermediate / advanced
                            CHECK (cooking_skill IN ('beginner', 'intermediate', 'advanced')),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id)
);

-- ============================================================
-- 3. ingredients  (재료 마스터)
-- ============================================================
CREATE TABLE ingredients (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    category    VARCHAR(50),                  -- 채소, 육류, 해산물, 유제품 등
    unit        VARCHAR(20),                  -- 기본 단위 (g, ml, 개 …)
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. user_fridge_items  (냉장고 재고)
-- ============================================================
CREATE TABLE user_fridge_items (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ingredient_id   INTEGER      NOT NULL REFERENCES ingredients(id),
    quantity        NUMERIC(10, 2) NOT NULL DEFAULT 0,
    unit            VARCHAR(20)  NOT NULL,
    expiry_date     DATE,                      -- 유통기한 (NULL = 미기재)
    storage_location VARCHAR(30) NOT NULL DEFAULT 'fridge'
                        CHECK (storage_location IN ('fridge', 'freezer', 'pantry', 'other')),
    freshness_score NUMERIC(3, 2)              -- 0.00 ~ 1.00
                        CHECK (freshness_score IS NULL OR freshness_score BETWEEN 0 AND 1),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fridge_user        ON user_fridge_items(user_id);
CREATE INDEX idx_fridge_expiry      ON user_fridge_items(user_id, expiry_date);

-- ============================================================
-- 5. recipes  (레시피 마스터)
-- ============================================================
CREATE TABLE recipes (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    cooking_time    INTEGER      NOT NULL CHECK (cooking_time > 0),  -- 분 단위
    difficulty      VARCHAR(20)  NOT NULL DEFAULT 'easy'
                        CHECK (difficulty IN ('easy', 'medium', 'hard')),
    steps           JSONB        NOT NULL DEFAULT '[]',  -- [{order, instruction}, ...]
    tool_tags       TEXT[]       NOT NULL DEFAULT '{}',  -- pan, oven, pot 등
    dietary_tags    TEXT[]       NOT NULL DEFAULT '{}',  -- vegan, gluten_free 등
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recipes_cooking_time ON recipes(cooking_time);
CREATE INDEX idx_recipes_tool_tags    ON recipes USING GIN(tool_tags);
CREATE INDEX idx_recipes_dietary_tags ON recipes USING GIN(dietary_tags);

-- ============================================================
-- 6. recipe_ingredients  (레시피-재료 매핑)
-- ============================================================
CREATE TABLE recipe_ingredients (
    id              SERIAL PRIMARY KEY,
    recipe_id       INTEGER      NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id   INTEGER      NOT NULL REFERENCES ingredients(id),
    quantity        NUMERIC(10, 2) NOT NULL,
    unit            VARCHAR(20)  NOT NULL,
    is_required     BOOLEAN      NOT NULL DEFAULT TRUE,   -- 필수 재료 여부
    is_garnish      BOOLEAN      NOT NULL DEFAULT FALSE,  -- 고명/장식 여부
    UNIQUE (recipe_id, ingredient_id)
);

CREATE INDEX idx_recipe_ing_recipe ON recipe_ingredients(recipe_id);

-- ============================================================
-- 7. ingredient_substitutions  (대체 재료 매핑)
-- ============================================================
CREATE TABLE ingredient_substitutions (
    id                  SERIAL PRIMARY KEY,
    original_ingredient_id  INTEGER NOT NULL REFERENCES ingredients(id),
    substitute_ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
    substitution_ratio  NUMERIC(5, 2) NOT NULL DEFAULT 1.0, -- 대체 비율 (원재료 1 기준)
    note                TEXT,                               -- 맛/향 차이 메모
    CHECK (original_ingredient_id <> substitute_ingredient_id),
    UNIQUE (original_ingredient_id, substitute_ingredient_id)
);

CREATE INDEX idx_sub_original ON ingredient_substitutions(original_ingredient_id);

-- ============================================================
-- 8. recommendation_logs  (추천 요청/결과 저장)
-- ============================================================
CREATE TABLE recommendation_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_text    TEXT         NOT NULL,       -- 사용자 원문 입력
    context_json    JSONB        NOT NULL DEFAULT '{}', -- 요청 시점 컨텍스트 (재고, 선호 등)
    result_json     JSONB        NOT NULL DEFAULT '{}', -- 추천 결과 (route, candidates 등)
    route           VARCHAR(20)                  -- COOK_NOW / SUBSTITUTION / SHOPPING_NEEDED
                        CHECK (route IN ('COOK_NOW', 'SUBSTITUTION', 'SHOPPING_NEEDED')),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rec_log_user ON recommendation_logs(user_id);
CREATE INDEX idx_rec_log_created ON recommendation_logs(created_at DESC);

-- ============================================================
-- 9. cooking_history  (조리 이력 및 피드백)
-- ============================================================
CREATE TABLE cooking_history (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id       INTEGER      NOT NULL REFERENCES recipes(id),
    rating          SMALLINT                     -- 1 ~ 5점 (NULL = 미평가)
                        CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    liked           BOOLEAN,                     -- 좋아요 여부
    feedback_text   TEXT,                        -- 자유 텍스트 피드백
    cooked_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_history_user   ON cooking_history(user_id);
CREATE INDEX idx_history_recipe ON cooking_history(recipe_id);
