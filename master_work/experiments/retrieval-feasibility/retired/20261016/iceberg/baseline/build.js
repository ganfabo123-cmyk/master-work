const fs = require('fs');
const path = require('path');
const root = __dirname;
if (process.env.FIXTURE_BUILD_FAILURE === '1') {
  console.error("head : The term 'head' is not recognized as a name of a cmdlet, function, script file, or executable program.");
  console.error('EPERM: operation not permitted, scandir .react-router/types/app/routes');
  process.exit(1);
}
const dist = path.join(root, 'dist');
fs.mkdirSync(dist, {recursive: true});
fs.copyFileSync(path.join(root, 'src', 'index.html'), path.join(dist, 'index.html'));
console.log('iceberg fixture build complete');
