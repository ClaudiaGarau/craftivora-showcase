/**
 * Portfolio-safe excerpt: validated product-to-catalog pipeline.
 * AI providers, storage and customer data are intentionally abstracted.
 */
export type ProductDraft = {
  name: string;
  category: string;
  language: 'it' | 'en';
  sourceUrl?: string;
};

export type CatalogJob = ProductDraft & {
  slug: string;
  status: 'queued' | 'needs-review';
};

const slugify = (value: string) => value
  .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
  .toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export function createCatalogJob(draft: ProductDraft): CatalogJob {
  if (draft.name.trim().length < 3) throw new Error('name is required');
  if (!draft.category.trim()) throw new Error('category is required');
  return { ...draft, slug: slugify(draft.name), status: 'needs-review' };
}

export function approveJob(job: CatalogJob): CatalogJob {
  return { ...job, status: 'queued' };
}
