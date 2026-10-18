const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..');
if (process.env.FIXTURE_BUILD_FAILURE === '1') {
  console.error('a11y_no_noninteractive_element_to_interactive_role: <article> has role="button"');
  process.exit(1);
}
const dist = path.join(root, 'dist');
fs.mkdirSync(dist, {recursive: true});
fs.writeFileSync(path.join(dist, 'index.html'), '<!doctype html><title>MyDatabase fixture</title><main>ORV</main>\n');
console.log('fixture frontend build complete');
