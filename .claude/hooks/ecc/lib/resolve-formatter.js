#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

function findProjectRoot(startDir) {
  let dir = startDir;
  while (dir !== path.dirname(dir)) {
    if (fs.existsSync(path.join(dir, 'package.json'))) return dir;
    dir = path.dirname(dir);
  }
  return null;
}

function detectFormatter(projectRoot) {
  if (!projectRoot) return null;
  const biomeConfigs = ['biome.json', 'biome.jsonc', '.biome.json'];
  for (const cfg of biomeConfigs) {
    if (fs.existsSync(path.join(projectRoot, cfg))) return 'biome';
  }
  const prettierConfigs = ['.prettierrc', '.prettierrc.json', '.prettierrc.js', 'prettier.config.js'];
  for (const cfg of prettierConfigs) {
    if (fs.existsSync(path.join(projectRoot, cfg))) return 'prettier';
  }
  return null;
}

function resolveFormatterBin(formatter, projectRoot) {
  if (!formatter || !projectRoot) return null;
  const localBin = path.join(projectRoot, 'node_modules', '.bin', formatter);
  if (fs.existsSync(localBin) || fs.existsSync(localBin + '.cmd')) return localBin;
  return formatter; // fall back to global
}

module.exports = { findProjectRoot, detectFormatter, resolveFormatterBin };
