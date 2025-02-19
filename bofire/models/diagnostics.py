from typing import Optional, Sequence

import numpy as np
import pandas as pd
from pydantic import root_validator, validator
from scipy.stats import fisher_exact, pearsonr, spearmanr
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)

from bofire.domain.util import PydanticBaseModel, is_numeric
from bofire.utils.enum import RegressionMetricsEnum


def _mean_absolute_error(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Calculates the mean absolute error.

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: mean absolute error
    """
    return mean_absolute_error(observed, predicted)


def _mean_squared_error(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Calculates the mean squared error.

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: mean squared error
    """
    return mean_squared_error(observed, predicted)


def _mean_absolute_percentage_error(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Calculates the mean percentage error.

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: mean percentage error
    """
    return mean_absolute_percentage_error(observed, predicted)


def _r2_score(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Calculates the R2 score.

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: R2 score.
    """
    return float(r2_score(observed, predicted))


def _pearson(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Calculates the Pearson correlation coefficient.

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: Pearson correlation coefficient.
    """
    with np.errstate(invalid="ignore"):
        rho, _ = pearsonr(predicted, observed)
    return float(rho)


def _spearman(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Calculates the Spearman correlation coefficient.

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: Spearman correlation coefficient.
    """
    with np.errstate(invalid="ignore"):
        rho, _ = spearmanr(predicted, observed)
    return float(rho)


def _fisher_exact_test_p(
    observed: np.ndarray,
    predicted: np.ndarray,
    standard_deviation: Optional[np.ndarray] = None,
) -> float:
    """Test if the model is able to distuinguish the bottom half of the observations from the top half.

    For this purpose Fisher's excat test is used together with the observations and predictions. The
    p value is returned. A low p value indicates that the model has some ability to distuiguish high from
    low values. A high p value indcates that the model cannot identify the difference or that the
    observations are too noisy to be able to tell.

    This implementation is taken from Ax: https://github.com/facebook/Ax/blob/main/ax/modelbridge/cross_validation.py

    Args:
        observed (np.ndarray): Observed data.
        predicted (np.ndarray): Predicted data.
        standard_deviation (Optional[np.ndarray], optional): Predicted standard deviation.
            Ignored in the calculation. Defaults to None.

    Returns:
        float: p value of the test.
    """
    n_half = len(observed) // 2
    top_obs = observed.argsort(axis=0)[-n_half:]
    top_est = predicted.argsort(axis=0)[-n_half:]
    # Construct contingency table
    tp = len(set(top_est).intersection(top_obs))
    fp = n_half - tp
    fn = n_half - tp
    tn = (len(observed) - n_half) - (n_half - tp)
    table = np.array([[tp, fp], [fn, tn]])
    # Compute the test statistic
    _, p = fisher_exact(table, alternative="greater")
    return float(p)


metrics = {
    RegressionMetricsEnum.MAE: _mean_absolute_error,
    RegressionMetricsEnum.MSD: _mean_squared_error,
    RegressionMetricsEnum.R2: _r2_score,
    RegressionMetricsEnum.MAPE: _mean_absolute_percentage_error,
    RegressionMetricsEnum.PEARSON: _pearson,
    RegressionMetricsEnum.SPEARMAN: _spearman,
    RegressionMetricsEnum.FISHER: _fisher_exact_test_p,
}


class CvResult(PydanticBaseModel):
    """Container representing the results of one CV fold.

    Attributes:
        key (str): Key of the validated output feature.
        observed (pd.Series): Series holding the observed values
        predicted (pd.Series): Series holding the predicted values
        standard_deviation (pd.Series, optional): Series holding the standard deviation associated with
            the prediction. Defaults to None.
    """

    key: str
    observed: pd.Series
    predicted: pd.Series
    standard_deviation: Optional[pd.Series] = None
    labcodes: Optional[pd.Series] = None
    X: Optional[pd.DataFrame] = None

    @root_validator(pre=True)
    def validate_shapes(cls, values):
        if not len(values["predicted"]) == len(values["observed"]):
            raise ValueError(
                f"Predicted values has length {len(values['predicted'])} whereas observed has length {len(values['observed'])}"
            )
        if "standard_deviation" in values and values["standard_deviation"] is not None:
            if not len(values["predicted"]) == len(values["standard_deviation"]):
                raise ValueError(
                    f"Predicted values has length {len(values['predicted'])} whereas standard_deviation has length {len(values['standard_deviation'])}"
                )
        if "labcodes" in values and values["labcodes"] is not None:
            if not len(values["predicted"]) == len(values["labcodes"]):
                raise ValueError(
                    f"Predicted values has length {len(values['predicted'])} whereas labcodes has length {len(values['labcodes'])}"
                )
        if "X" in values and values["X"] is not None:
            if not len(values["predicted"]) == len(values["X"]):
                raise ValueError(
                    f"Predicted values has length {len(values['predicted'])} whereas X has length {len(values['X'])}"
                )
        return values

    @validator("observed")
    def validate_observed(cls, v, values):
        if not is_numeric(v):
            raise ValueError("Not all values of observed are numerical")
        return v

    @validator("predicted")
    def validate_predicted(cls, v, values):
        if not is_numeric(v):
            raise ValueError("Not all values of predicted are numerical")
        return v

    @validator("standard_deviation")
    def validate_standard_deviation(cls, v, values):
        if v is not None:
            if not is_numeric(v):
                raise ValueError("Not all values of standard_deviation are numerical")
        return v

    @property
    def n_samples(self) -> int:
        """Returns the number of samples in the fold.

        Returns:
            int: Number of samples in the split.
        """
        return len(self.observed)

    def get_metric(self, metric: RegressionMetricsEnum) -> float:
        """Calculates a metric for the fold.

        Args:
            metric (RegressionMetricsEnum): Metric to calculate.

        Returns:
            float: Metric value.
        """
        if self.n_samples == 1:
            raise ValueError("Metric cannot be calculated for only one sample.")
        return metrics[metric](self.observed.values, self.predicted.values, self.standard_deviation)  # type: ignore


class CvResults(PydanticBaseModel):
    """Container holding all cv folds of a cross-validation run.

    Attributes:
        results (Sequence[CvResult]: Sequence of `CvResult` objects.
    """

    results: Sequence[CvResult]

    @validator("results")
    def validate_results(cls, v, values):
        if len(v) <= 1:
            raise ValueError("`results` sequence has to contain at least two elements.")
        key = v[0].key
        for i in v:
            if i.key != key:
                raise ValueError("`CvResult` objects do not match.")
        for field in ["standard_deviation", "labcodes", "X"]:
            has_field = getattr(v[0], field) is not None
            for i in v:
                has_i = getattr(i, field) is not None
                if has_field != has_i:
                    raise ValueError(
                        f"Either all or none `CvResult` objects contain {field}."
                    )
        # check columns of X
        if v[0].X is not None:
            cols = sorted(list(v[0].X.columns))
            for i in v:
                if sorted(list(i.X.columns)) != cols:
                    raise ValueError("Columns of X do not match.")
        return v

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def __getitem__(self, i) -> CvResult:
        return self.results[i]

    @property
    def key(self) -> str:
        """Returns name of the feature for which the cross validation was performed.

        Returns:
            str: feature name.
        """
        return self.results[0].key

    @property
    def is_loo(self) -> bool:
        """Checks if the object represents a LOO-CV

        Returns:
            bool: True if LOO-CV else False.
        """
        return (np.array([r.n_samples for r in self.results]) == 1).all()

    def _combine_folds(self) -> CvResult:
        """Combines the `CvResult` splits into one flat array for predicted, observed and standard_deviation.

        Returns:
            Tuple[np.ndarray, np.ndarray, Union[np.ndarray, None]]: One pd.Series for CvResult property.
        """
        observed = pd.concat([cv.observed for cv in self.results], ignore_index=True)
        predicted = pd.concat([cv.predicted for cv in self.results], ignore_index=True)
        if self.results[0].standard_deviation is not None:
            sd = pd.concat([cv.standard_deviation for cv in self.results], ignore_index=True)  # type: ignore
        else:
            sd = None
        if self.results[0].labcodes is not None:
            labcodes = pd.concat([cv.labcodes for cv in self.results], ignore_index=True)  # type: ignore
        else:
            labcodes = None
        if self.results[0].X is not None:
            X = pd.concat([cv.X for cv in self.results], ignore_index=True)  # type: ignore
        else:
            X = None
        return CvResult(
            key=self.results[0].key,
            observed=observed,
            predicted=predicted,
            standard_deviation=sd,
            labcodes=labcodes,
            X=X,
        )

    def get_metric(
        self, metric: RegressionMetricsEnum, combine_folds: bool = True
    ) -> pd.Series:
        """Calculates a metric for every fold and returns them as pd.Series.

        Args:
            metric (RegressionMetricsEnum): Metrics to calculate.
            combine_folds (bool, optional): If True the data in the split is combined before
                the metric is calculated. In this case only a single number is returned. If False
                the metric is calculated per fold. Defaults to True.

        Returns:
            pd.Series: Object containing the metric value for every fold.
        """
        if self.is_loo or combine_folds:
            return pd.Series(
                self._combine_folds().get_metric(metric=metric), name=metric.name
            )
        return pd.Series(
            [cv.get_metric(metric) for cv in self.results], name=metric.name
        )

    def get_metrics(
        self,
        metrics: Sequence[RegressionMetricsEnum] = [
            RegressionMetricsEnum.MAE,
            RegressionMetricsEnum.MSD,
            RegressionMetricsEnum.R2,
            RegressionMetricsEnum.MAPE,
            RegressionMetricsEnum.PEARSON,
            RegressionMetricsEnum.SPEARMAN,
            RegressionMetricsEnum.FISHER,
        ],
        combine_folds: bool = True,
    ) -> pd.DataFrame:
        """Calculates all metrics provided as list for every fold and returns all as pd.DataFrame.

        Args:
            metrics (Sequence[RegressionMetricsEnum], optional): Metrics to calculate. Defaults to R2, MAE, MSD, R2, MAPE.
            combine_folds (bool, optional): If True the data in the split is combined before
                the metric is calculated. In this case only a single number per metric is returned. If False
                the metric is calculated per fold. Defaults to True.

        Returns:
            pd.DataFrame: Dataframe containing the metric values for all folds.
        """
        return pd.concat([self.get_metric(m, combine_folds) for m in metrics], axis=1)
