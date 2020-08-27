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

import java.io.IOException;

import com.consts.Constants.EnumCellDoFree;
import com.consts.Constants.EnumCellMdMethod;
import com.consts.Constants.EnumHybridFunc;
import com.consts.Constants.EnumHybridTreat;
import com.consts.Constants.EnumIonMdMethod;
import com.consts.Constants.EnumThermalstat;
import com.consts.Constants.EnumUnitTime;
import com.consts.Constants.EnumVdw;

import core.agent.InputAgent;
import core.agent.WrapperBoolean;
import core.agent.WrapperDouble;
import core.agent.WrapperEnum;
import core.agent.WrapperInteger;

public class InputAgentMd extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3123568374548375634L;
	
	public WrapperInteger mdSteps;
	public WrapperDouble timeStep;
	public WrapperEnum enumTimeUnit;
	public WrapperBoolean boolMoveCell;
	public WrapperEnum enumMdMethodIon;
	public WrapperBoolean boolNoSym;
	
	public WrapperEnum enumThermalstat;
	public WrapperDouble temperature;
	public WrapperDouble tolp;
	public WrapperInteger nraise;
	public WrapperDouble deltat;
	
	public WrapperEnum enumMdMethodCell;
	public WrapperDouble pressure;
	public WrapperEnum enumCellDoFree;
	
	public InputAgentMd() {
		
		mdSteps = new WrapperInteger(50);
		timeStep = new WrapperDouble(20.0);
		enumTimeUnit = new WrapperEnum(EnumUnitTime.Ry);
		boolNoSym = new WrapperBoolean(false); 
				
		enumMdMethodIon = new WrapperEnum(EnumIonMdMethod.verlet);
		enumThermalstat = new WrapperEnum(EnumThermalstat.non);
		temperature = new WrapperDouble(300.0);
		tolp = new WrapperDouble(100.0);
		nraise = new WrapperInteger(1);
		deltat = new WrapperDouble(1.0);
		
		boolMoveCell = new WrapperBoolean(false);
		enumMdMethodCell = new WrapperEnum(EnumCellMdMethod.pr);
		pressure = new WrapperDouble(0.0);
		enumCellDoFree = new WrapperEnum(EnumCellDoFree.all);
	}
	//for compatibility 
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for default loading after serialization
	    in.defaultReadObject();
	    //no symmetry, added in v0.3.0
	    if(boolNoSym==null) {boolNoSym = new WrapperBoolean(false);}
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		// TODO Auto-generated method stub
		return false;
	}
}
