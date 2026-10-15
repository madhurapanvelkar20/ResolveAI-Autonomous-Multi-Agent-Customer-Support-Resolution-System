import { afterEach, describe, expect, it, vi } from 'vitest';
import { createCase } from '../api';

describe('API error formatting', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('formats structured validation details without object coercion', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ['body', 'message'], msg: 'Message cannot be blank' },
          { loc: ['body', 'customer_id'], msg: 'Invalid identifier' },
        ],
      }),
    }));

    await expect(createCase({ customer_id: 'bad!id', message: '' }))
      .rejects.toThrow('body.message: Message cannot be blank; body.customer_id: Invalid identifier');
  });
});
