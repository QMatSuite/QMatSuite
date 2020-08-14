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
package agent;

import com.consts.Constants.EnumCellDoFree;
import com.consts.Constants.EnumCellOptMethod;
import com.consts.Constants.EnumIonOptMethod;
import com.consts.Constants.EnumUnitEnergy;

import core.agent.InputAgent;

public class InputAgentOpt extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -8527007056845124155L;
	
	public WrapperBoolean boolRelaxCell,
	boolScfMustConverge;
	public WrapperInteger nMaxSteps;
	
	public WrapperDouble numEConv,
	numFConv,
	numPConv,
	numPTarget;
	
	public WrapperEnum enumEUnit,
	enumOptMethodIon,
	enumOptMethodCell,
	enumCellDoFree;
	
	
	public InputAgentOpt() {
		
		boolRelaxCell = new WrapperBoolean(false);
		boolScfMustConverge = new WrapperBoolean(true);
		nMaxSteps = new WrapperInteger(50);
		
		numEConv = new WrapperDouble(1e-4);
		numFConv = new WrapperDouble(1e-3);
		numPConv = new WrapperDouble(0.5);
		numPTarget = new WrapperDouble(0.0);
		
		enumEUnit = new WrapperEnum(EnumUnitEnergy.Ry);
		enumOptMethodIon = new WrapperEnum(EnumIonOptMethod.bfgs);
		enumOptMethodCell = new WrapperEnum(EnumCellOptMethod.bfgs);
		enumCellDoFree = new WrapperEnum(EnumCellDoFree.all);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		// TODO Auto-generated method stub
		return false;
	}
}
