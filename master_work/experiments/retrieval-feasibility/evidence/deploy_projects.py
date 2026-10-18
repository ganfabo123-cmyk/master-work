import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def write(base, name, content):
    path = base/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content,str) else json.dumps(content,indent=2)+'\n',encoding='utf-8')

for arm in ('baseline','managed'):
    epilog = ROOT/'experiments/retrieval-feasibility/fixtures/epilog'/arm
    write(epilog, 'build.bat', '@echo off\nclang -std=c11 -Wall -Wextra -Wpedantic -Iinclude main.c repl.c internals/atoms.c internals/variables.c internals/terms.c parser/lexer.c parser/parser.c engine/database.c engine/unifier.c engine/builtins.c engine/solver.c -o epilog.exe\n')
    write(epilog, 'query.pl', 'parent(alice, bob).\nparent(bob, carol).\ngrandparent(X, Y) :- parent(X, Z), parent(Z, Y).\n?- grandparent(alice, carol).\nhalt.\n')
    write(epilog, 'README.md', '# Epilog\n\nBuild with `./build.bat`. Run `Get-Content query.pl | ./epilog.exe`.\n')
    ice = ROOT/'experiments/retrieval-feasibility/fixtures/iceberg'/arm
    write(ice, 'package.json', {'name':'iceberg','private':True,'type':'module','scripts':{'dev':'react-router dev','build':'react-router build','typecheck':'react-router typegen && tsc'},'dependencies':{'isbot':'5.1.44','react':'19.2.3','react-dom':'19.2.3','react-router':'7.15.1','@react-router/node':'7.15.1','@react-router/serve':'7.15.1'},'devDependencies':{'@react-router/dev':'7.15.1','vite':'6.3.5','typescript':'5.8.3','@types/node':'22.15.30','@types/react':'19.2.2','@types/react-dom':'19.2.2','@tailwindcss/vite':'4.1.8','tailwindcss':'4.1.8','vite-tsconfig-paths':'5.1.4'}})
    write(ice, 'vite.config.ts', 'import { reactRouter } from "@react-router/dev/vite";\nimport { defineConfig } from "vite";\nimport tailwindcss from "@tailwindcss/vite";\nimport tsconfigPaths from "vite-tsconfig-paths";\nexport default defineConfig({plugins:[tailwindcss(),reactRouter(),tsconfigPaths()]});\n')
    write(ice, 'app/routes.ts', 'import { type RouteConfig, index } from "@react-router/dev/routes";\nexport default [index("routes/home.tsx")] satisfies RouteConfig;\n')
    write(ice, 'README.md', '# IceBerg\n\n`npm run dev` starts the website. `npm run build` creates a production build.\n')
    db = ROOT/'experiments/retrieval-feasibility/fixtures/mydatabase'/arm/'frontend'
    write(db, 'package.json', {'name':'mydatabase-frontend','private':True,'type':'module','scripts':{'dev':'vite dev','build':'vite build','preview':'vite preview'},'devDependencies':{'@sveltejs/kit':'2.70.3','@sveltejs/adapter-auto':'7.0.1','@sveltejs/vite-plugin-svelte':'7.3.1','svelte':'5.57.2','vite':'8.0.14','sass':'1.105.2','typescript':'5.8.3'}})
    write(db,'tsconfig.json',{'extends':'./.svelte-kit/tsconfig.json','compilerOptions':{'allowJs':True,'checkJs':True,'esModuleInterop':True,'forceConsistentCasingInFileNames':True,'resolveJsonModule':True,'skipLibCheck':True,'sourceMap':True,'strict':True,'moduleResolution':'bundler'}})
    write(db,'README.md','# MyDatabase frontend\n\n`npm run build` builds the database browser. `npm run dev` starts development.\n')
    # Only the managed arm receives the existing DSH plugin overlay.
    if arm == 'managed':
        for name in ('epilog','iceberg','mydatabase'):
            overlay = ROOT/'experiments/retrieval-feasibility/retired/20261016'/name/'managed/skill-runtime-hint.cordis.yml'
            write(ROOT/'experiments/retrieval-feasibility/fixtures'/name/arm,'skill-runtime-hint.cordis.yml',overlay.read_text(encoding='utf-8'))


