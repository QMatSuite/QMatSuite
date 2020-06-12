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
package main.java.agent;

import java.util.ArrayList;

import main.java.app.input.geo.Element;
import main.java.com.consts.Constants.EnumMixingMode;
import main.java.com.consts.Constants.EnumOccupations;
import main.java.com.consts.Constants.EnumSmearing;
import main.java.com.consts.Constants.EnumUnitEnergy;
import main.java.com.consts.Constants.ProgramName;

public class InputAgentScf extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3659165710616979269L;
	public Boolean setMag,
	setU,
	setHybrid,
	setVdw,
	setAdv,
	setE;
	public Boolean expandStandard,
	expandMag,
	expandU,
	expandHybrid,
	expandVdw,
	expandAdv,
	expandE;
	
	//standard
	public WrapperEnum enumOccupation;//EnumOccupations 
	public WrapperBoolean boolRestart;
	public WrapperBoolean boolForce;
	public WrapperBoolean boolStress;
	public WrapperEnum enumEnergyUnit;
	public WrapperDouble  ecutWfc,
	ecutRho,
	elecConv,
	mixBeta,
	degauss;
	public WrapperInteger nElecMaxStep,
	nkx,
	nky,
	nkz;
	public WrapperEnum enumMixing;//EnumMixingMode
	public WrapperEnum enumSmearing;//EnumSmearing
	
	//magnet
	public WrapperInteger nspin;
	public WrapperBoolean noncolin;
	public WrapperBoolean boolSoc;
	public WrapperBoolean setForElements;
	public WrapperBoolean setForAtoms;
	//hubbardU
	//public WrapperBoolean boolHubbardU;
	public WrapperBoolean lda_plus_u;
	public ArrayList<Element> elementList;
	
	public InputAgentScf() {
		super(ProgramName.PW);
		//************************|***********//
		//***********************\|/**********//
		//*******already dealt with in PwInput//
		//general
		setMag=false;setU=false;setHybrid=false;
		setVdw=false;setAdv=false;setE=false;
		expandStandard=false;expandMag=false;expandU=false;expandHybrid=false;
		expandVdw=false;expandAdv=false;expandE=false;
		//spin
		nspin=new WrapperInteger(1);noncolin=new WrapperBoolean(false);boolSoc=new WrapperBoolean(false);//ok
		setForElements=new WrapperBoolean(false);//ok
		setForAtoms = new WrapperBoolean(false);//ok
		//DFT+U
		//boolHubbardU=new WrapperBoolean(false);
		lda_plus_u=new WrapperBoolean(false);//ok
		elementList = new ArrayList<Element>();//ok, //for scfHubbard, part of all elements
		//standard
		boolRestart=new WrapperBoolean(false); //false is from scratch //ok
		boolForce=new WrapperBoolean(false);boolStress=new WrapperBoolean(false);enumOccupation=new WrapperEnum(EnumOccupations.smearing);//ok
		enumEnergyUnit = new WrapperEnum(EnumUnitEnergy.Ry);//ok
		ecutWfc = new WrapperDouble(null);//ok
		ecutRho = new WrapperDouble(null);//ok
		nElecMaxStep=new WrapperInteger(100);elecConv=new WrapperDouble(1e-6);enumMixing=new WrapperEnum(EnumMixingMode.plain);
		mixBeta=new WrapperDouble(0.7);//ok
		nkx = new WrapperInteger(1);//ok
		nky = new WrapperInteger(1);//ok
		nkz = new WrapperInteger(1);//ok
		enumSmearing=new WrapperEnum(EnumSmearing.gauss);//ok
		degauss = new WrapperDouble(0.0);//ok
		//***********************/|\*********//
		//************************|**********//
		
	}
	
}
