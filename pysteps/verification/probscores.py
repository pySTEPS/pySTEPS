"""Evaluation and skill scores for probabilistic forecasts."""

import numpy as np

def CRPS(X_f, X_o):
    """Compute the average continuous ranked probability score (CRPS) for a set 
    of forecast ensembles and the corresponding observations.
    
    Parameters
    ----------
    X_f : array_like
      Array of shape (n,m) containing n ensembles of forecast values with each 
      ensemble having m members.
    X_o : array_like
      Array of n observed values.
    
    Returns
    -------
    out : float
      The continuous ranked probability score.
    
    References
    ----------
    .. [Her2000] H. Hersbach, "Decomposition of the Continuous Ranked Probability 
                 Score for Ensemble Prediction Systems", Weather and Forecasting, 
                 15(5), 559-570, 2000, 
                 doi:10.1175/1520-0434(2000)015<0559:DOTCRP>2.0.CO;2.
    
    """
    mask = np.logical_and(np.all(np.isfinite(X_f), axis=1), np.isfinite(X_o))
    
    X_f = X_f[mask, :].copy()
    X_f.sort(axis=1)
    X_o = X_o[mask]
    
    n = X_f.shape[0]
    m = X_f.shape[1]
    
    alpha = np.zeros((n, m+1))
    beta  = np.zeros((n, m+1))
    
    for i in range(1, m):
        mask = X_o > X_f[:, i]
        alpha[mask, i] = X_f[mask, i] - X_f[mask, i-1]
        beta[mask, i]  = 0.0
        
        mask = np.logical_and(X_f[:, i] > X_o, X_o > X_f[:, i-1])
        alpha[mask, i] = X_o[mask] - X_f[mask, i-1]
        beta[mask, i]  = X_f[mask, i] - X_o[mask]
        
        mask = X_o < X_f[:, i-1]
        alpha[mask, i] = 0.0
        beta[mask, i]  = X_f[mask, i] - X_f[mask, i-1]
    
    mask = X_o < X_f[:, 0]
    alpha[mask, 0] = 0.0
    beta[mask, 0]  = X_f[mask, 0] - X_o[mask]
    
    mask = X_f[:, -1] < X_o
    alpha[mask, -1] = X_o[mask] - X_f[mask, -1]
    beta[mask, -1]  = 0.0
    
    p = 1.0*np.arange(m+1) / m
    res = np.sum(alpha*p**2.0 + beta*(1.0-p)**2.0, axis=1)
    
    return np.mean(res)

def reldiag_init(X_min, n_bins=10, min_count=10):
    """Initialize a reliability diagram object.
    
    Parameters
    ----------
    X_min : float
      Precipitation intensity threshold for yes/no prediction.
    n_bins : int
        Number of bins to use in the reliability diagram.
    min_count : int
      Minimum number of samples required for each bin. A zero value is assigned 
      if the number of samples in a bin is smaller than bin_count.
    
    Returns
    -------
    out : dict
      The reliability diagram object.
    
    References
    ----------
    .. [BS2007] J. Brocker and L.A. Smith. "Increasing the Reliability of 
                Reliability Diagrams", Weather and Forecasting, 22(3), 651-661, 
                2007, doi:10.1175/WAF993.1.
    
    """
    reldiag = {}
    
    reldiag["X_min"]       = X_min
    reldiag["bin_edges"]   = np.linspace(-1e-6, 1+1e-6, n_bins+1)
    reldiag["n_bins"]      = n_bins
    reldiag["X_sum"]       = np.zeros(n_bins)
    reldiag["Y_sum"]       = np.zeros(n_bins, dtype=int)
    reldiag["num_idx"]     = np.zeros(n_bins, dtype=int)
    reldiag["sample_size"] = np.zeros(n_bins, dtype=int)
    reldiag["min_count"]   = min_count
    
    return reldiag

def reldiag_accum(reldiag, P_f, X_o):
    """Accumulate the given probability-observation pairs into the reliability 
    diagram.
    
    Parameters
    ----------
    reldiag : dict
      A reliability diagram object created with reldiag_init.
    P_f : array-like
      Forecast probabilities for exceeding the intensity threshold specified 
      in the reliability diagram object.
    X_o : array-like
      Observed values.
    """
    mask = np.logical_and(np.isfinite(P_f), np.isfinite(X_o))
    
    P_f = P_f[mask]
    X_o = X_o[mask]
    
    idx = np.digitize(P_f, reldiag["bin_edges"], right=True)
    
    x       = []
    y       = []
    num_idx = []
    ss      = []
    
    for k in range(1, len(reldiag["bin_edges"])):
        I_k = np.where(idx == k)[0]
        if len(I_k) >= reldiag["min_count"]:
            X_o_above_thr = (X_o[I_k] >= reldiag["X_min"]).astype(int)
            y.append(np.sum(X_o_above_thr))
            x.append(np.sum(P_f[I_k]))
            num_idx.append(len(I_k))
            ss.append(len(I_k))
        else:
            y.append(0.0)
            x.append(0.0)
            num_idx.append(0.0)
            ss.append(0)
    
    reldiag["X_sum"]       += np.array(x)
    reldiag["Y_sum"]       += np.array(y, dtype=int)
    reldiag["num_idx"]     += np.array(num_idx, dtype=int)
    reldiag["sample_size"] += ss

def reldiag_compute(reldiag):
    """Compute the x- and y- coordinates of the points in the reliability diagram.
    
    Parameters
    ----------
    reldiag : dict
      A reliability diagram object created with reldiag_init.
    
    Returns
    -------
    out : tuple
      Two-element tuple containing the x- and y-coordinates of the points in 
      the reliability diagram.
    """
    f = 1.0 * reldiag["Y_sum"] / reldiag["num_idx"]
    r = 1.0 * reldiag["X_sum"] / reldiag["num_idx"]
    
    return r,f

def ROC_curve_init(X_min, n_prob_thrs=10):
    """Initialize a ROC curve object.
    
    Parameters
    ----------
    X_min : float
      Precipitation intensity threshold for yes/no prediction.
    n_prob_thrs : int
      The number of probability thresholds to use. The interval [0,1] is divided 
      into n_prob_thrs evenly spaced values.
    
    Returns
    -------
    out : dict
      The ROC curve object.
    """
    ROC = {}
    
    ROC["X_min"]        = X_min
    ROC["hits"]         = np.zeros(n_prob_thrs, dtype=int)
    ROC["misses"]       = np.zeros(n_prob_thrs, dtype=int)
    ROC["false_alarms"] = np.zeros(n_prob_thrs, dtype=int)
    ROC["corr_neg"]     = np.zeros(n_prob_thrs, dtype=int)
    ROC["prob_thrs"]    = np.linspace(0.0, 1.0, n_prob_thrs)
    
    return ROC

def ROC_curve_accum(ROC, P_f, X_o):
    """Accumulate the given probability-observation pairs into the given ROC 
    object.
    
    Parameters
    ----------
    ROC : dict
      A ROC curve object created with ROC_curve_init.
    P_f : array_like
      Forecasted probabilities for exceeding the threshold specified in the ROC 
      object. Non-finite values are ignored.
    X_o : array_like
      Observed values. Non-finite values are ignored.
    """
    mask = np.logical_and(np.isfinite(P_f), np.isfinite(X_o))
    
    P_f = P_f[mask]
    X_o = X_o[mask]
    
    for i,p in enumerate(ROC["prob_thrs"]):
        mask = np.logical_and(P_f >= p, X_o >= ROC["X_min"])
        ROC["hits"][i]         += np.sum(mask.astype(int))
        mask = np.logical_and(P_f <  p, X_o >= ROC["X_min"])
        ROC["misses"][i]       += np.sum(mask.astype(int))
        mask = np.logical_and(P_f >= p, X_o <  ROC["X_min"])
        ROC["false_alarms"][i] += np.sum(mask.astype(int))
        mask = np.logical_and(P_f <  p, X_o <  ROC["X_min"])
        ROC["corr_neg"][i]     += np.sum(mask.astype(int))

def ROC_curve_compute(ROC, compute_area=False):
    """Compute the ROC curve and its area from the given ROC object.
    
    Parameters
    ----------
    ROC : dict
      A ROC curve object created with ROC_curve_init.
    compute_area : bool
      If True, compute the area under the ROC curve (between 0.5 and 1).
    
    Returns
    -------
    out : tuple
      A two-element tuple containing the probability of detection (POD) and 
      probability of false detection (POFD) for the probability thresholds 
      specified in the ROC curve object. If compute_area is True, return the 
      area under the ROC curve as the third element of the tuple.
    """
    POD_vals  = []
    POFD_vals = []
    
    for i in range(len(ROC["prob_thrs"])):
        POD_vals.append(1.0*ROC["hits"][i] / (ROC["hits"][i] + ROC["misses"][i]))
        POFD_vals.append(1.0*ROC["false_alarms"][i] / \
                         (ROC["corr_neg"][i] + ROC["false_alarms"][i]))
    
    if compute_area:
        # Compute the total area of parallelepipeds under the ROC curve.
        area = (1.0 - POFD_vals[0]) * (1.0 + POD_vals[0]) / 2.0
        for i in range(len(ROC["prob_thrs"])-1):
          area += (POFD_vals[i] - POFD_vals[i+1]) * (POD_vals[i+1] + POD_vals[i]) / 2.0
        area += POFD_vals[-1] * POD_vals[-1] / 2.0
        
        return POFD_vals,POD_vals,area
    else:
        return POFD_vals,POD_vals
