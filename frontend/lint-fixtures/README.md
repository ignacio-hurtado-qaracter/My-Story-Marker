# lint-fixtures

A miniature `src/` tree that plants one violation per boundary rule of spec 002,
FR-STATIC-02. `test/lint.test.ts` lints it with the project's `eslint.config.js` (type-aware
rules off) and asserts that each file raises exactly the rule named in its `// expect:` header,
or nothing when the header says `none` (AC 3). It is excluded from the normal lint run and
from every build.
