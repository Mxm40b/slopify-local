

create main.py, search.py, log.py, move everything to src/


write better prompts

create graphs for everything a given model will see

add config file to select main, helper, and decision models from ollama


edit pipeline to give main model thoughts: env, facts, and plan md files


switch to openai api if better perf needed



idea: because the platform is only for agents,
maybe llama.cpp can give options to ask for a very specific format of response.
in that case:
thoughts until done
most likely useful list of tools to be run

instead of a single main model that runs tools as it currently works.





searching pipeline:

main model: some search arguments that i need to decide for, eg either specific search terms or vague ideas with an objective in mind

searcher model: gets what main model is asking for, makes different searches which each provide about ten results with the links, snippets, titles.
searcher model: flags the interesting sites to visit, asks the parser to look for some specific info in each. (note: its prompt will ask it to prefer raw sites, sites known for not having only js, etc)

parser model: gets the main model's question, the searcher model's prompt, the searcher model's rationale and general idea of what it expects from that site, and gets the entire site (if the site isn't too long) passed through trafilatura

same as below, the search is summarized by small models and given back to the large model




current idea for pipeline:

user: prompt
small model: rewrite prompt according to strict guidelines to make it more understandable; expose to decision model, and until the decision model decides that the rewrite is faithful enough and good enough, the small model rewrites.
main model: briefed on its context, and given the prompt.

in loop:
main model: inspects environment via ls_tool and read_tool
main model: prompts small models for specific tasks, and writes to itself a goal that that task is supposed to accomplish
main model: chooses which executables to ask for, then asks for them.
main model: asks small models to cross-check other models'
main model: periodically edits facts.md (not subjective), env.md (not subjective), plan.md (vague, can change)

helper models: have full access to the shell, can exit by requesting more tools, saying they cannot do some or some other thing, that they failed, or that they succeeded.


rewriter models: when the main model runs out of tokens, the small models separate its thinking into chapters, sub-chapters, etc. with a precise description of what each contains
rewriter models: once the chapters are selected, each piece of info from the main model's thoughts is moved to one chapter
rewriter checkers: decision models that have the entire rewritten chapters, the original thoughts, and a selection of a few lines, and for each selection, say if they are important, and if they are important, whether the important parts have been correctly added.
rewriter checkers: for each chapter, decision on whether accurate enough. if not, rewriters prompted again to rewrite what was written in that chapter.

rewriter models: once chapters and contents are verified, with a strict routine, they condense the chapters of the memory.
checkers: using same principles as before, check that everything was correctly compacted



last 20% of thoughts of main model are kept, everything above is replaced with rewritten content


note: only three models are actually loaded in memory; one large, one small, one decision, but their memories are duplicated: there are many memory versions of the small model, for example, for each task


idea: socratic questionning to verify facts a tiny bit more reliably, eg two small models prompting each other
