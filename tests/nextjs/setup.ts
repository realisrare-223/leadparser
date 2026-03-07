/**
 * Vitest global setup — runs before every test file.
 *
 * Imports @testing-library/jest-dom matchers so we can use
 * `expect(element).toBeInTheDocument()` etc. in all tests.
 */
import '@testing-library/jest-dom'
