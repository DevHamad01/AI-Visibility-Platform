import { FormControl } from '@angular/forms';
import { describe, expect, it } from 'vitest';
import { domainValidator } from './brand-form';
describe('domain validation', () => {
  it.each(['example.com', 'https://example.com/path', 'sub.example.co.uk'])(
    'accepts the backend-compatible input %s',
    (value) => expect(domainValidator(new FormControl(value))).toBeNull(),
  );
  it.each(['', 'localhost', '-bad.com', 'bad-.com', 'hello world.com', 'example.com:80'])(
    'rejects %s before saving',
    (value) => expect(domainValidator(new FormControl(value))).toEqual({ domain: true }),
  );
});
