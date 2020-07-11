/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.programconst;

public interface DefaultFileNames {
	public final String defaultSettingFile = "settings.ini";
	public final String calcSaveFile = "save.calc";
	public final String projSaveFile = "save.proj";
	
	public final String bandsDatGnu = "bands.out.gnu";
	
	public final String pseudoDojoDir = "pseudo_dojo_ONCVPSP_v0.4";
	public final String psLibraryDir = "PSlibrary_v1.0.0";
	public final String ssspDir = "SSSP_v1.1";
	
	public enum SettingKeys {
		workspace,
		pseudolibroot,
		qePath
	}
}
