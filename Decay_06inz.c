/* Initialization */
#include "Decay_model.h"
#include "Decay_11mix.h"
#include "Decay_12jac.h"
#if defined(__cplusplus)
extern "C" {
#endif

void Decay_functionInitialEquations_0(DATA *data, threadData_t *threadData);

/*
equation index: 1
type: SIMPLE_ASSIGN
x = $START.x
*/
void Decay_eqFunction_1(DATA *data, threadData_t *threadData)
{
  const int equationIndexes[2] = {1,1};
  (data->localData[0]->realVars[data->simulationInfo->realVarsIndex[0]] /* x STATE(1) */) = ((modelica_real *)((data->modelData->realVarsData[0] /* x STATE(1) */).attribute .start.data))[0];
  threadData->lastEquationSolved = 1;
}
extern void Decay_eqFunction_3(DATA *data, threadData_t *threadData);

OMC_DISABLE_OPT
void Decay_functionInitialEquations_0(DATA *data, threadData_t *threadData)
{
  static void (*const eqFunctions[2])(DATA*, threadData_t*) = {
    Decay_eqFunction_1,
    Decay_eqFunction_3
  };
  
  for (int id = 0; id < 2; id++) {
    eqFunctions[id](data, threadData);
  }
}

int Decay_functionInitialEquations(DATA *data, threadData_t *threadData)
{
  data->simulationInfo->discreteCall = 1;
  Decay_functionInitialEquations_0(data, threadData);
  data->simulationInfo->discreteCall = 0;
  
  return 0;
}

/* No Decay_functionInitialEquations_lambda0 function */

int Decay_functionRemovedInitialEquations(DATA *data, threadData_t *threadData)
{
  const int *equationIndexes = NULL;
  double res = 0.0;

  
  return 0;
}


#if defined(__cplusplus)
}
#endif
