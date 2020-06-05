/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package project;

public class ProjectCalcLog {

    private String project = null;
    private String calculation = null;
    private String calcType = null;
    private String status = null;

    public ProjectCalcLog() {
    }

    public ProjectCalcLog(String pj, String cc, String ct, String st) {
        this.project = pj;
        this.calculation = cc;
        this.calcType = ct;
        this.status = st;
    }
    //get
    public String getProject() {
        return project;
    }
    public String getCalculation() {
        return calculation;
    }
    public String getStatus() {
        return status;
    }
    //set
    public void setProject(String pj) {
        this.project = pj;
    }
    public void setCalculation(String cc) {
        this.calculation = cc;
    }
    public void setStatus(String st) {
        this.status = st;
    }

	public String getCalcType() {
		return calcType;
	}

	public void setCalcType(String calcType) {
		this.calcType = calcType;
	}
}
