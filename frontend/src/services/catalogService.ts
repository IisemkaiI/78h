/** Public catalog calls against `/api/v1/catalog`. */

import { apiRequest } from './apiClient';
import type {
  CatalogCourseDetail,
  CatalogPage,
  CatalogSort,
  Category,
  CourseLevel,
} from '../types/api';

const CATALOG_PREFIX = '/api/v1/catalog';

export interface CatalogQuery {
  search?: string;
  category?: string;
  level?: CourseLevel | '';
  language?: string;
  sort?: CatalogSort;
  page?: number;
  pageSize?: number;
}

function buildQuery(params: CatalogQuery): string {
  const query = new URLSearchParams();
  if (params.search?.trim()) {
    query.set('search', params.search.trim());
  }
  if (params.category) {
    query.set('category', params.category);
  }
  if (params.level) {
    query.set('level', params.level);
  }
  if (params.language?.trim()) {
    query.set('language', params.language.trim().toLowerCase());
  }
  if (params.sort) {
    query.set('sort', params.sort);
  }
  if (params.page !== undefined) {
    query.set('page', String(params.page));
  }
  if (params.pageSize !== undefined) {
    query.set('page_size', String(params.pageSize));
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : '';
}

export function listCategories(signal?: AbortSignal): Promise<Category[]> {
  return apiRequest<Category[]>(`${CATALOG_PREFIX}/categories`, { signal });
}

export function listCatalogCourses(
  params: CatalogQuery = {},
  signal?: AbortSignal,
): Promise<CatalogPage> {
  return apiRequest<CatalogPage>(`${CATALOG_PREFIX}/courses${buildQuery(params)}`, { signal });
}

export function getCatalogCourse(slug: string, signal?: AbortSignal): Promise<CatalogCourseDetail> {
  return apiRequest<CatalogCourseDetail>(
    `${CATALOG_PREFIX}/courses/${encodeURIComponent(slug)}`,
    { signal },
  );
}
