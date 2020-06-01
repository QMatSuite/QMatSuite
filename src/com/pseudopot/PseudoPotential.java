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
package com.pseudopot;

import java.util.ArrayList;

import com.consts.Constants.EnumFunctional;
import com.consts.Constants.EnumPP;

public abstract class PseudoPotential {
	protected EnumPseudoPotLib libName;
	protected ArrayList<EnumFunctional> functionalList;//functional list
	protected ArrayList<EnumPP> ppList;//pseudopotential type list
	protected ArrayList<String> precisionList;//precision settings
	boolean fullRelativSupport;
	
	public PseudoPotential(EnumPseudoPotLib ln, boolean fr) {
		libName = ln;
		functionalList = new ArrayList<EnumFunctional>();
		ppList = new ArrayList<EnumPP>();
		precisionList = new ArrayList<String>();
		fullRelativSupport = fr;
	}
	public ArrayList<EnumFunctional> getFunctionalList(){
		return functionalList;
	}
	public ArrayList<EnumPP> getPpList(){
		return ppList;
	}
	public ArrayList<String> getPrecisionList(){
		return precisionList;
	}
	public boolean getFullRelativSupport() {
		return fullRelativSupport;
	}
}
