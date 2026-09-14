export async function resolve(specifier, context, nextResolve) {
  if (specifier === '@kabelsalat/web') {
    return {
      url: new URL('./kabelsalat-stub.mjs', import.meta.url).href,
      shortCircuit: true,
    };
  }
  return nextResolve(specifier, context);
}
