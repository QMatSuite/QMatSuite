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

import java.io.File;

import com.consts.Constants.EnumFunctional;
import com.pseudopot.SSSPEnum.Efficiency;
import com.pseudopot.SSSPEnum.Precision;

public class SSSPClass extends PseudoPotential{

	private String precString = "Efficiency";
	
	public SSSPClass() {
		super(EnumPseudoPotLib.SSSP, false);
		precisionList.add("Efficiency");precisionList.add("Precision");
		functionalList.add(EnumFunctional.PBE);
	}
	public String getFile(String element) { //element name in the format of e.g. "He" 
		if (precString==null || !precisionList.contains(precString)) return null;
		if (precString.equals("Efficiency")) {
			try {
				Efficiency ef = Efficiency.valueOf(element);
				return ef.getFolderName()+File.separator+ef.getFileName();
			}
			catch (IllegalArgumentException iae) {
				return null;
			}
		}
		else if (precString.equals("Precision")) {
			try {
				Precision ef = Precision.valueOf(element);
				return ef.getFolderName()+File.separator+ef.getFileName();
			}
			catch (IllegalArgumentException iae) {
				return null;
			}
		}
		else return null;
	}

	public String getPrecString() {
		return precString;
	}

	public void setPrecString(String ps) {
		//need to take null!!
		precString = ps;
	}

}
