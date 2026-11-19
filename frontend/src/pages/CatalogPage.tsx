import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { CourseCard } from '../components/course/CourseCard';
import { listCategories, listCatalogCourses } from '../services/catalogService';
import type {
  CatalogPage,
  CatalogSort,
  Category,
  CourseLevel,
} from '../types/api';
import { describeCourseError } from '../utils/courseErrors';
import '../styles/catalog.css';

const PAGE_SIZE = 9;

interface Filters {
  search: string;
  category: string;
  level: CourseLevel | '';
  language: string;
  sort: CatalogSort;
}

const EMPTY_FILTERS: Filters = {
  search: '',
  category: '',
  level: '',
  language: '',
  sort: 'newest',
};

export function CatalogPage() {
  const { status, user } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [searchInput, setSearchInput] = useState('');
  const [languageInput, setLanguageInput] = useState('');
  const [page, setPage] = useState(1);
  const [catalog, setCatalog] = useState<CatalogPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canAuthor = user?.permissions.includes('courses:create') ?? false;

  useEffect(() => {
    const controller = new AbortController();
    listCategories(controller.signal)
      .then(setCategories)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    listCatalogCourses({ ...filters, page, pageSize: PAGE_SIZE }, controller.signal)
      .then((result) => {
        setCatalog(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(describeCourseError(caught));
        setLoading(false);
      });

    return () => controller.abort();
  }, [filters, page]);

  const hasActiveFilters = useMemo(
    () =>
      filters.search !== '' ||
      filters.category !== '' ||
      filters.level !== '' ||
      filters.language !== '' ||
      filters.sort !== 'newest',
    [filters],
  );

  const applyFilters = (next: Partial<Filters>): void => {
    setFilters((previous) => ({ ...previous, ...next }));
    setPage(1);
  };

  const handleSearch = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    applyFilters({
      search: searchInput.trim(),
      language: languageInput.trim().toLowerCase(),
    });
  };

  const resetFilters = (): void => {
    setSearchInput('');
    setLanguageInput('');
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  return (
    <main className="page">
      <header className="page__heading catalog-hero">
        <p className="eyebrow">Каталог курсов</p>
        <h1 className="page__title">Учитесь тому, что важно сейчас</h1>
        <p className="muted">
          Публичные курсы платформы: программирование, дизайн, аналитика, языки и другие
          направления. Черновики и архивные курсы здесь не показываются.
        </p>
        {status === 'authenticated' && canAuthor && (
          <div className="catalog-hero__actions">
            <Link className="button button--primary" to="/author">
              Мои курсы
            </Link>
          </div>
        )}
      </header>

      <form className="catalog-filters card" onSubmit={handleSearch} role="search">
        <label className="field catalog-filters__search">
          <span className="field__label">Поиск</span>
          <input
            className="input"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Название или краткое описание"
          />
        </label>

        <label className="field">
          <span className="field__label">Категория</span>
          <select
            className="input"
            value={filters.category}
            onChange={(event) => applyFilters({ category: event.target.value })}
          >
            <option value="">Все категории</option>
            {categories.map((category) => (
              <option key={category.id} value={category.slug}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field__label">Уровень</span>
          <select
            className="input"
            value={filters.level}
            onChange={(event) =>
              applyFilters({ level: event.target.value as CourseLevel | '' })
            }
          >
            <option value="">Любой уровень</option>
            <option value="beginner">Начальный</option>
            <option value="intermediate">Средний</option>
            <option value="advanced">Продвинутый</option>
          </select>
        </label>

        <label className="field">
          <span className="field__label">Язык</span>
          <input
            className="input"
            type="text"
            value={languageInput}
            onChange={(event) => setLanguageInput(event.target.value)}
            placeholder="ru, en…"
            maxLength={10}
          />
        </label>

        <label className="field">
          <span className="field__label">Сортировка</span>
          <select
            className="input"
            value={filters.sort}
            onChange={(event) =>
              applyFilters({ sort: event.target.value as CatalogSort })
            }
          >
            <option value="newest">Сначала новые</option>
            <option value="oldest">Сначала старые</option>
            <option value="title">По названию</option>
          </select>
        </label>

        <div className="catalog-filters__actions">
          <button type="submit" className="button button--primary">
            Искать
          </button>
          {hasActiveFilters && (
            <button type="button" className="button button--ghost" onClick={resetFilters}>
              Сбросить
            </button>
          )}
        </div>
      </form>

      {error !== null && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      {loading && (
        <p className="page__status" role="status">
          Загрузка каталога…
        </p>
      )}

      {!loading && catalog !== null && catalog.items.length === 0 && (
        <div className="card stack catalog-empty">
          <h2>Ничего не найдено</h2>
          <p className="muted">
            Попробуйте изменить запрос или сбросить фильтры. В каталоге пока могут быть не
            опубликованы курсы.
          </p>
          {hasActiveFilters && (
            <button type="button" className="button button--ghost" onClick={resetFilters}>
              Сбросить фильтры
            </button>
          )}
        </div>
      )}

      {!loading && catalog !== null && catalog.items.length > 0 && (
        <>
          <p className="muted catalog-count" role="status">
            Найдено курсов: {catalog.total}
          </p>
          <div className="catalog-grid">
            {catalog.items.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>

          {catalog.pages > 1 && (
            <nav className="pagination" aria-label="Страницы каталога">
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={catalog.page <= 1}
              >
                Назад
              </button>
              <span className="pagination__status">
                Страница {catalog.page} из {catalog.pages}
              </span>
              <button
                type="button"
                className="button button--ghost button--sm"
                onClick={() => setPage((current) => Math.min(catalog.pages, current + 1))}
                disabled={catalog.page >= catalog.pages}
              >
                Вперёд
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  );
}
