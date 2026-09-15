import { approveJob, createCatalogJob } from './catalog-pipeline';

describe('catalog pipeline', () => {
  it('normalizes a draft and stops for human review', () => {
    const job = createCatalogJob({ name: 'Cute Axolotl Pattern', category: 'patterns', language: 'en' });
    expect(job.slug).toBe('cute-axolotl-pattern');
    expect(job.status).toBe('needs-review');
  });

  it('rejects incomplete product metadata', () => {
    expect(() => createCatalogJob({ name: 'x', category: '', language: 'it' })).toThrow();
  });

  it('requires an explicit approval transition', () => {
    const job = createCatalogJob({ name: 'Pattern', category: 'patterns', language: 'it' });
    expect(approveJob(job).status).toBe('queued');
  });
});
