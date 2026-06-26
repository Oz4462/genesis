/* Main Simulation File */

#if defined(__cplusplus)
extern "C" {
#endif

#include "Decay_model.h"
#include "simulation/solver/events.h"
#include "util/real_array.h"

/* FIXME these defines are ugly and hard to read, why not use direct function pointers instead? */
#define prefixedName_performSimulation Decay_performSimulation
#define prefixedName_updateContinuousSystem Decay_updateContinuousSystem
#include <simulation/solver/perform_simulation.c.inc>

#define prefixedName_performQSSSimulation Decay_performQSSSimulation
#include <simulation/solver/perform_qss_simulation.c.inc>


/* dummy VARINFO and FILEINFO */
const VAR_INFO dummyVAR_INFO = omc_dummyVarInfo;

int Decay_input_function(DATA *data, threadData_t *threadData)
{
  
  return 0;
}

int Decay_input_function_init(DATA *data, threadData_t *threadData)
{
  
  return 0;
}

int Decay_input_function_updateStartValues(DATA *data, threadData_t *threadData)
{
  
  return 0;
}

int Decay_inputNames(DATA *data, char ** names){
  
  return 0;
}

int Decay_data_function(DATA *data, threadData_t *threadData)
{
  return 0;
}

int Decay_dataReconciliationInputNames(DATA *data, char ** names){
  
  return 0;
}

int Decay_dataReconciliationUnmeasuredVariables(DATA *data, char ** names)
{
  
  return 0;
}

int Decay_output_function(DATA *data, threadData_t *threadData)
{
  
  return 0;
}

int Decay_setc_function(DATA *data, threadData_t *threadData)
{
  
  return 0;
}

int Decay_setb_function(DATA *data, threadData_t *threadData)
{
  
  return 0;
}


/*
equation index: 3
type: SIMPLE_ASSIGN
$DER.x = -x
*/
void Decay_eqFunction_3(DATA *data, threadData_t *threadData)
{
  const int equationIndexes[2] = {1,3};
  (data->localData[0]->realVars[data->simulationInfo->realVarsIndex[1]] /* der(x) STATE_DER */) = (-(data->localData[0]->realVars[data->simulationInfo->realVarsIndex[0]] /* x STATE(1) */));
  threadData->lastEquationSolved = 3;
}

OMC_DISABLE_OPT
int Decay_functionDAE(DATA *data, threadData_t *threadData)
{
  int equationIndexes[1] = {0};
#if !defined(OMC_MINIMAL_RUNTIME)
  if (measure_time_flag) rt_tick(SIM_TIMER_DAE);
#endif

  data->simulationInfo->needToIterate = 0;
  data->simulationInfo->discreteCall = 1;
  Decay_functionLocalKnownVars(data, threadData);
  static void (*const eqFunctions[1])(DATA*, threadData_t*) = {
    Decay_eqFunction_3
  };
  
  for (int id = 0; id < 1; id++) {
    eqFunctions[id](data, threadData);
  }
  data->simulationInfo->discreteCall = 0;
  
#if !defined(OMC_MINIMAL_RUNTIME)
  if (measure_time_flag) rt_accumulate(SIM_TIMER_DAE);
#endif
  return 0;
}


int Decay_functionLocalKnownVars(DATA *data, threadData_t *threadData)
{
  
  return 0;
}

/* forwarded equations */
extern void Decay_eqFunction_3(DATA* data, threadData_t *threadData);

static void functionODE_system0(DATA *data, threadData_t *threadData)
{
  static void (*const eqFunctions[1])(DATA*, threadData_t*) = {
    Decay_eqFunction_3
  };
  
  for (int id = 0; id < 1; id++) {
    eqFunctions[id](data, threadData);
  }
}

int Decay_functionODE(DATA *data, threadData_t *threadData)
{
#if !defined(OMC_MINIMAL_RUNTIME)
  if (measure_time_flag) rt_tick(SIM_TIMER_FUNCTION_ODE);
#endif

  
  data->simulationInfo->callStatistics.functionODE++;
  
  Decay_functionLocalKnownVars(data, threadData);
  functionODE_system0(data, threadData);

#if !defined(OMC_MINIMAL_RUNTIME)
  if (measure_time_flag) rt_accumulate(SIM_TIMER_FUNCTION_ODE);
#endif

  return 0;
}

/* forward the main in the simulation runtime */
extern int _main_SimulationRuntime(int argc, char **argv, DATA *data, threadData_t *threadData);
extern int _main_OptimizationRuntime(int argc, char **argv, DATA *data, threadData_t *threadData);

#include "Decay_12jac.h"
#include "Decay_13opt.h"

struct OpenModelicaGeneratedFunctionCallbacks Decay_callback = {
  (int (*)(DATA *, threadData_t *, void *)) Decay_performSimulation,    /* performSimulation */
  (int (*)(DATA *, threadData_t *, void *)) Decay_performQSSSimulation,    /* performQSSSimulation */
  Decay_updateContinuousSystem,    /* updateContinuousSystem */
  Decay_callExternalObjectDestructors,    /* callExternalObjectDestructors */
  NULL,    /* initialNonLinearSystem */
  NULL,    /* initialLinearSystem */
  NULL,    /* initialMixedSystem */
  #if !defined(OMC_NO_STATESELECTION)
  Decay_initializeStateSets,
  #else
  NULL,
  #endif    /* initializeStateSets */
  Decay_initializeDAEmodeData,
  Decay_functionODE,
  Decay_functionAlgebraics,
  Decay_functionDAE,
  Decay_functionLocalKnownVars,
  Decay_input_function,
  Decay_input_function_init,
  Decay_input_function_updateStartValues,
  Decay_data_function,
  Decay_output_function,
  Decay_setc_function,
  Decay_setb_function,
  Decay_function_storeDelayed,
  Decay_function_storeSpatialDistribution,
  Decay_function_initSpatialDistribution,
  Decay_updateBoundVariableAttributes,
  Decay_functionInitialEquations,
  GLOBAL_EQUIDISTANT_HOMOTOPY,
  NULL,
  Decay_functionRemovedInitialEquations,
  Decay_updateBoundParameters,
  Decay_checkForAsserts,
  Decay_function_ZeroCrossingsEquations,
  Decay_function_ZeroCrossings,
  Decay_function_updateRelations,
  Decay_zeroCrossingDescription,
  Decay_relationDescription,
  Decay_function_initSample,
  Decay_INDEX_JAC_A,
  Decay_INDEX_JAC_B,
  Decay_INDEX_JAC_C,
  Decay_INDEX_JAC_D,
  Decay_INDEX_JAC_F,
  Decay_INDEX_JAC_H,
  Decay_initialAnalyticJacobianA,
  Decay_initialAnalyticJacobianB,
  Decay_initialAnalyticJacobianC,
  Decay_initialAnalyticJacobianD,
  Decay_initialAnalyticJacobianF,
  Decay_initialAnalyticJacobianH,
  Decay_functionJacA_column,
  Decay_functionJacB_column,
  Decay_functionJacC_column,
  Decay_functionJacD_column,
  Decay_functionJacF_column,
  Decay_functionJacH_column,
  Decay_linear_model_frame,
  Decay_linear_model_datarecovery_frame,
  Decay_mayer,
  Decay_lagrange,
  Decay_getInputVarIndicesInOptimization,
  Decay_pickUpBoundsForInputsInOptimization,
  Decay_setInputData,
  Decay_getTimeGrid,
  Decay_symbolicInlineSystem,
  Decay_function_initSynchronous,
  Decay_function_updateSynchronous,
  Decay_function_equationsSynchronous,
  Decay_inputNames,
  Decay_dataReconciliationInputNames,
  Decay_dataReconciliationUnmeasuredVariables,
  NULL,
  NULL,
  NULL,
  NULL,
  -1,
  NULL,
  NULL,
  -1

};

#define _OMC_LIT_RESOURCE_0_name_data "Decay"
#define _OMC_LIT_RESOURCE_0_dir_data "."
static const MMC_DEFSTRINGLIT(_OMC_LIT_RESOURCE_0_name,5,_OMC_LIT_RESOURCE_0_name_data);
static const MMC_DEFSTRINGLIT(_OMC_LIT_RESOURCE_0_dir,1,_OMC_LIT_RESOURCE_0_dir_data);

static const MMC_DEFSTRUCTLIT(_OMC_LIT_RESOURCES,2,MMC_ARRAY_TAG) {MMC_REFSTRINGLIT(_OMC_LIT_RESOURCE_0_name), MMC_REFSTRINGLIT(_OMC_LIT_RESOURCE_0_dir)}};
void Decay_setupDataStruc(DATA *data, threadData_t *threadData)
{
  assertStreamPrint(threadData,0!=data, "Error while initialize Data");
  threadData->localRoots[LOCAL_ROOT_SIMULATION_DATA] = data;
  data->callback = &Decay_callback;
  OpenModelica_updateUriMapping(threadData, MMC_REFSTRUCTLIT(_OMC_LIT_RESOURCES));
  data->modelData->modelName = "Decay";
  data->modelData->modelFilePrefix = "Decay";
  data->modelData->modelFileName = "<interactive>";
  data->modelData->resultFileName = NULL;
  data->modelData->modelDir = "";
  data->modelData->modelGUID = "{fbc7bcf8-95db-4e10-bcf0-b32070c6d998}";
  #if defined(OPENMODELICA_XML_FROM_FILE_AT_RUNTIME)
  data->modelData->initXMLData = NULL;
  data->modelData->modelDataXml.infoXMLData = NULL;
  #else
  #if defined(_MSC_VER) /* handle joke compilers */
  {
  /* for MSVC we encode a string like char x[] = {'a', 'b', 'c', '\0'} */
  /* because the string constant limit is 65535 bytes */
  static const char contents_init[] =
    #include "Decay_init.c"
    ;
  static const char contents_info[] =
    #include "Decay_info.c"
    ;
    data->modelData->initXMLData = contents_init;
    data->modelData->modelDataXml.infoXMLData = contents_info;
  }
  #else /* handle real compilers */
  data->modelData->initXMLData =
  #include "Decay_init.c"
    ;
  data->modelData->modelDataXml.infoXMLData =
  #include "Decay_info.c"
    ;
  #endif /* defined(_MSC_VER) */
  #endif /* defined(OPENMODELICA_XML_FROM_FILE_AT_RUNTIME) */
  data->modelData->modelDataXml.fileName = "Decay_info.json";
  data->modelData->resourcesDir = NULL;
  data->modelData->runTestsuite = 0;
  data->modelData->nStatesArray = 1;
  data->modelData->nDiscreteReal = 0;
  data->modelData->nVariablesRealArray = 2;
  data->modelData->nVariablesIntegerArray = 0;
  data->modelData->nVariablesBooleanArray = 0;
  data->modelData->nVariablesStringArray = 0;
  data->modelData->nParametersRealArray = 0;
  data->modelData->nParametersIntegerArray = 0;
  data->modelData->nParametersBooleanArray = 0;
  data->modelData->nParametersStringArray = 0;
  data->modelData->nParametersReal = 0;
  data->modelData->nParametersInteger = 0;
  data->modelData->nParametersBoolean = 0;
  data->modelData->nParametersString = 0;
  data->modelData->nAliasRealArray = 0;
  data->modelData->nAliasIntegerArray = 0;
  data->modelData->nAliasBooleanArray = 0;
  data->modelData->nAliasStringArray = 0;
  data->modelData->nInputVars = 0;
  data->modelData->nOutputVars = 0;
  data->modelData->nZeroCrossings = 0;
  data->modelData->nSamples = 0;
  data->modelData->nRelations = 0;
  data->modelData->nMathEvents = 0;
  data->modelData->nExtObjs = 0;
  data->modelData->modelDataXml.modelInfoXmlLength = 0;
  data->modelData->modelDataXml.nFunctions = 0;
  data->modelData->modelDataXml.nProfileBlocks = 0;
  data->modelData->modelDataXml.nEquations = 4;
  data->modelData->nMixedSystems = 0;
  data->modelData->nLinearSystems = 0;
  data->modelData->nNonLinearSystems = 0;
  data->modelData->nStateSets = 0;
  data->modelData->nJacobians = 6;
  data->modelData->nOptimizeConstraints = 0;
  data->modelData->nOptimizeFinalConstraints = 0;
  data->modelData->nDelayExpressions = 0;
  data->modelData->nBaseClocks = 0;
  data->modelData->nSpatialDistributions = 0;
  data->modelData->nSensitivityVars = 0;
  data->modelData->nSensitivityParamVars = 0;
  data->modelData->nSetcVars = 0;
  data->modelData->ndataReconVars = 0;
  data->modelData->nSetbVars = 0;
  data->modelData->nRelatedBoundaryConditions = 0;
  data->modelData->linearizationDumpLanguage = OMC_LINEARIZE_DUMP_LANGUAGE_MODELICA;
}

static int rml_execution_failed()
{
  fflush(NULL);
  fprintf(stderr, "Execution failed!\n");
  fflush(NULL);
  return 1;
}


#if defined(__MINGW32__) || defined(_MSC_VER)

#if !defined(_UNICODE)
#define _UNICODE
#endif
#if !defined(UNICODE)
#define UNICODE
#endif

#include <windows.h>
char** omc_fixWindowsArgv(int argc, wchar_t **wargv)
{
  char** newargv;
  /* Support for non-ASCII characters
  * Read the unicode command line arguments and translate it to char*
  */
  newargv = (char**)malloc(argc*sizeof(char*));
  for (int i = 0; i < argc; i++) {
    newargv[i] = omc_wchar_to_multibyte_str(wargv[i]);
  }
  return newargv;
}

#define OMC_MAIN wmain
#define OMC_CHAR wchar_t
#define OMC_EXPORT __declspec(dllexport) extern

#else
#define omc_fixWindowsArgv(N, A) (A)
#define OMC_MAIN main
#define OMC_CHAR char
#define OMC_EXPORT extern
#endif

#if defined(threadData)
#undef threadData
#endif
/* call the simulation runtime main from our main! */
#if defined(OMC_DLL_MAIN_DEFINE)
OMC_EXPORT int omcDllMain(int argc, OMC_CHAR **argv)
#else
int OMC_MAIN(int argc, OMC_CHAR** argv)
#endif
{
  char** newargv = omc_fixWindowsArgv(argc, argv);
  /*
    Set the error functions to be used for simulation.
    The default value for them is 'functions' version. Change it here to 'simulation' versions
  */
  omc_assert = omc_assert_simulation;
  omc_assert_withEquationIndexes = omc_assert_simulation_withEquationIndexes;

  omc_assert_warning_withEquationIndexes = omc_assert_warning_simulation_withEquationIndexes;
  omc_assert_warning = omc_assert_warning_simulation;
  omc_terminate = omc_terminate_simulation;
  omc_throw = omc_throw_simulation;

  int res;
  DATA data;
  MODEL_DATA modelData;
  SIMULATION_INFO simInfo;
  data.modelData = &modelData;
  data.simulationInfo = &simInfo;
  measure_time_flag = 0;
  compiledInDAEMode = 0;
  compiledWithSymSolver = 0;
  MMC_INIT(0);
  omc_alloc_interface.init();
  {
    MMC_TRY_TOP()
  
    MMC_TRY_STACK()
  
    Decay_setupDataStruc(&data, threadData);
    res = _main_initRuntimeAndSimulation(argc, newargv, &data, threadData);
    if(res == 0) {
      if (omc_flag[FLAG_MOO_OPTIMIZATION]) {
        res = _main_OptimizationRuntime(argc, newargv, &data, threadData);
      } else {
        res = _main_SimulationRuntime(argc, newargv, &data, threadData);
      }
    }
    
    MMC_ELSE()
    rml_execution_failed();
    fprintf(stderr, "Stack overflow detected and was not caught.\nSend us a bug report at https://trac.openmodelica.org/OpenModelica/newticket\n    Include the following trace:\n");
    printStacktraceMessages();
    fflush(NULL);
    return 1;
    MMC_CATCH_STACK()
    
    MMC_CATCH_TOP(return rml_execution_failed());
  }

  fflush(NULL);
  return res;
}

#ifdef __cplusplus
}
#endif


