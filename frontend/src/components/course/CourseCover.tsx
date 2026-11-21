interface CourseCoverProps {
  title: string;
  slug: string;
  category: string;
  imageUrl: string | null;
}

function variantFor(seed: string): 'moss' | 'clay' | 'lake' {
  const hash = Array.from(seed).reduce((value, character) => value + character.charCodeAt(0), 0);
  const variants = ['moss', 'clay', 'lake'] as const;
  return variants[hash % variants.length] ?? 'moss';
}

export function CourseCover({ title, slug, category, imageUrl }: CourseCoverProps) {
  if (imageUrl) {
    return <img className="course-cover__photo" src={imageUrl} alt="" loading="lazy" />;
  }

  const variant = variantFor(slug || title);
  return (
    <div className={`course-cover course-cover--${variant}`} aria-hidden="true">
      <span className="course-cover__eyebrow">ОТКРЫТЫЙ КУРС</span>
      <svg className="course-cover__art" viewBox="0 0 360 220" fill="none" focusable="false">
        <circle cx="260" cy="86" r="72" fill="currentColor" opacity=".12" />
        <path d="M214 31 335 72 282 179 161 138z" fill="currentColor" opacity=".12" />
        <rect x="170" y="57" width="137" height="98" rx="12" fill="var(--cover-paper)" transform="rotate(8 170 57)" />
        <rect x="190" y="81" width="88" height="7" rx="3.5" fill="currentColor" opacity=".32" transform="rotate(8 190 81)" />
        <rect x="185" y="101" width="105" height="7" rx="3.5" fill="currentColor" opacity=".2" transform="rotate(8 185 101)" />
        <rect x="180" y="121" width="68" height="7" rx="3.5" fill="var(--cover-accent)" transform="rotate(8 180 121)" />
        <path d="m61 97 31-26 32 26v49H61z" fill="var(--cover-accent)" opacity=".88" />
        <path d="M51 99 92 65l43 34" stroke="var(--cover-ink)" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="80" y="116" width="24" height="30" rx="3" fill="var(--cover-paper)" />
        <circle cx="290" cy="45" r="9" fill="var(--cover-accent)" />
        <circle cx="143" cy="161" r="6" fill="currentColor" opacity=".4" />
      </svg>
      <span className="course-cover__category">{category}</span>
      <strong className="course-cover__title">{title}</strong>
    </div>
  );
}
