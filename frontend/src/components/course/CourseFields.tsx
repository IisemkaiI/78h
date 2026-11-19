import type { Category, CourseLevel } from '../../types/api';

export interface CourseFormValues {
  title: string;
  short_description: string;
  description: string;
  cover_image_url: string;
  level: CourseLevel;
  language: string;
  category_id: string;
}

export const EMPTY_COURSE_FORM: CourseFormValues = {
  title: '',
  short_description: '',
  description: '',
  cover_image_url: '',
  level: 'beginner',
  language: 'ru',
  category_id: '',
};

export function courseFormFromValues(
  values: Omit<Partial<CourseFormValues>, 'cover_image_url'> & {
    category_id?: string;
    cover_image_url?: string | null;
  },
): CourseFormValues {
  return {
    title: values.title ?? '',
    short_description: values.short_description ?? '',
    description: values.description ?? '',
    cover_image_url: values.cover_image_url ?? '',
    level: values.level ?? 'beginner',
    language: values.language ?? 'ru',
    category_id: values.category_id ?? '',
  };
}

export function CourseFields({
  values,
  categories,
  disabled = false,
  onChange,
  idPrefix = 'course',
}: {
  values: CourseFormValues;
  categories: Category[];
  disabled?: boolean;
  onChange: (next: CourseFormValues) => void;
  idPrefix?: string;
}) {
  const set = <K extends keyof CourseFormValues>(key: K, value: CourseFormValues[K]): void => {
    onChange({ ...values, [key]: value });
  };

  return (
    <div className="form course-form">
      <label className="field" htmlFor={`${idPrefix}-title`}>
        <span className="field__label">Название *</span>
        <input
          id={`${idPrefix}-title`}
          className="input"
          type="text"
          value={values.title}
          onChange={(event) => set('title', event.target.value)}
          maxLength={200}
          disabled={disabled}
          placeholder="Например: Python с нуля"
        />
        <span className="field__hint">3–200 символов. Slug создаётся автоматически и не меняется.</span>
      </label>

      <label className="field" htmlFor={`${idPrefix}-short`}>
        <span className="field__label">Краткое описание *</span>
        <textarea
          id={`${idPrefix}-short`}
          className="input textarea"
          value={values.short_description}
          onChange={(event) => set('short_description', event.target.value)}
          maxLength={300}
          rows={2}
          disabled={disabled}
          placeholder="Одно-два предложения для карточки каталога"
        />
        <span className="field__hint">{values.short_description.length}/300 символов.</span>
      </label>

      <label className="field" htmlFor={`${idPrefix}-description`}>
        <span className="field__label">Полное описание *</span>
        <textarea
          id={`${idPrefix}-description`}
          className="input textarea"
          value={values.description}
          onChange={(event) => set('description', event.target.value)}
          maxLength={20000}
          rows={6}
          disabled={disabled}
          placeholder="Чему научится студент, для кого курс, какие темы внутри"
        />
      </label>

      <div className="course-form__row">
        <label className="field" htmlFor={`${idPrefix}-category`}>
          <span className="field__label">Категория *</span>
          <select
            id={`${idPrefix}-category`}
            className="input"
            value={values.category_id}
            onChange={(event) => set('category_id', event.target.value)}
            disabled={disabled}
          >
            <option value="">Выберите категорию</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field" htmlFor={`${idPrefix}-level`}>
          <span className="field__label">Уровень *</span>
          <select
            id={`${idPrefix}-level`}
            className="input"
            value={values.level}
            onChange={(event) => set('level', event.target.value as CourseLevel)}
            disabled={disabled}
          >
            <option value="beginner">Начальный</option>
            <option value="intermediate">Средний</option>
            <option value="advanced">Продвинутый</option>
          </select>
        </label>

        <label className="field" htmlFor={`${idPrefix}-language`}>
          <span className="field__label">Язык *</span>
          <input
            id={`${idPrefix}-language`}
            className="input"
            type="text"
            value={values.language}
            onChange={(event) => set('language', event.target.value)}
            maxLength={10}
            disabled={disabled}
            placeholder="ru"
          />
        </label>
      </div>

      <label className="field" htmlFor={`${idPrefix}-cover`}>
        <span className="field__label">Ссылка на обложку</span>
        <input
          id={`${idPrefix}-cover`}
          className="input"
          type="url"
          value={values.cover_image_url}
          onChange={(event) => set('cover_image_url', event.target.value)}
          maxLength={500}
          disabled={disabled}
          placeholder="https://example.com/cover.jpg"
        />
        <span className="field__hint">Необязательно. Абсолютный адрес http(s).</span>
      </label>
    </div>
  );
}
